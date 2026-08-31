from django.conf import settings
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from domain_launch_assistant.users.models import User

from .serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data["refresh"]).blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class GoogleAuthView(APIView):
    """
    Sign in (or sign up) using a Google ID token.

    Frontend flow: Google Identity Services (@react-oauth/google) returns a
    signed JWT "credential" after the user picks a Google account — no
    OAuth redirect dance needed on our end. We verify that JWT's signature
    against Google's public certs (google-auth handles fetching/caching
    the certs), then get_or_create a User by email and hand back the same
    {access, refresh, user} shape LoginView returns, so the frontend can
    treat this identically to a normal login.

    If no account exists yet for that email, one is created here — Google
    sign-in doubles as registration, there's no separate "register with
    Google" endpoint.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        credential = request.data.get("credential")
        if not credential:
            return Response(
                {"detail": "credential is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            id_info = google_id_token.verify_oauth2_token(
                credential,
                google_auth_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return Response(
                {"detail": "Invalid Google credential."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = id_info.get("email")
        if not email:
            return Response(
                {"detail": "Google account has no email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Email is unique+indexed on User (see users/models.py), so this is
        # also how an existing password-based account gets linked the
        # first time its owner uses "Continue with Google".
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": id_info.get("given_name", ""),
                "last_name": id_info.get("family_name", ""),
            },
        )
        if created:
            # No password was ever set for a Google-only account — mark it
            # unusable rather than leaving an empty/guessable password.
            user.set_unusable_password()
            user.save(update_fields=["password"])

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )