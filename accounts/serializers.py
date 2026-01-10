import logging

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserProfile

logger = logging.getLogger(__name__)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["bio", "discord_username", "notifications_enabled", "theme"]


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "avatar",
            "is_admin",
            "profile",
            "created_at",
        ]
        read_only_fields = ["id", "role", "is_admin", "created_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
        ]

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Les mots de passe ne correspondent pas"})
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(**validated_data)
        UserProfile.objects.create(user=user)
        return user


class TokenObtainSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])

        if not user:
            raise serializers.ValidationError("Identifiants incorrects")

        if not user.is_active:
            raise serializers.ValidationError("Ce compte a été désactivé")

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user, context={"request": self.context["request"]}).data,
        }


class UserUpdateSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "avatar", "profile"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)

        if "avatar" in validated_data and instance.avatar:
            old_avatar_name = instance.avatar.name
            old_avatar_storage = instance.avatar.storage
            try:
                if old_avatar_storage.exists(old_avatar_name):
                    old_avatar_storage.delete(old_avatar_name)
                    logger.info(
                        f"[accounts_serializers] Ancien avatar supprimé pour l'utilisateur {instance.id}: {old_avatar_name}"
                    )
            except Exception as e:
                logger.warning(
                    "[accounts_serializers] Erreur lors de la suppression de l'ancien avatar "
                    f"pour l'utilisateur {instance.id}: {str(e)}"
                )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe incorrect")
        return value
