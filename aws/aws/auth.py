"""AWS authentication: standard credential chain + STS role assumption with file-based caching."""
from __future__ import annotations

import time
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .cache import Cache
from .config import Config
from .exceptions import AuthError
from .logger import get_logger

log = get_logger("auth")

# Refresh assumed-role credentials this many seconds before they expire.
_REFRESH_BUFFER_S: int = 300


class Auth:
    """Manages boto3 Sessions.

    Role credentials are cached on disk (via :class:`Cache`) so that repeated
    calls within the same TTL window do not incur additional STS round-trips.
    """

    def __init__(self, config: Config, cache: Cache) -> None:
        self._config = config
        self._cache = cache
        # In-memory session pool: avoids re-calling STS within the same process.
        self._sessions: dict[str, boto3.Session] = {}

    # ── Public ────────────────────────────────────────────────────────────────

    def session(
        self,
        profile: str | None = None,
        region: str | None = None,
        role: str | None = None,
    ) -> boto3.Session:
        """Return a :class:`boto3.Session`, optionally after assuming *role*.

        *role* may be an alias defined in the config file or a bare ARN.
        """
        profile = profile or self._config.get("profile")
        region = region or self._config.get("region", "us-east-1")
        effective_role = role or self._config.get("role")
        role_arn: str | None = self._config.role_arn(effective_role) if effective_role else None
        if effective_role and not role_arn:
            raise AuthError(f"Unknown role alias: {effective_role!r}")

        pool_key = f"{profile}:{region}:{role_arn}"
        if pool_key in self._sessions:
            return self._sessions[pool_key]

        try:
            kwargs: dict[str, Any] = {"region_name": region}
            if profile:
                kwargs["profile_name"] = profile
            base = boto3.Session(**kwargs)

            if role_arn:
                sess = self._assume_role(base, role_arn, region or "us-east-1")
            else:
                self._validate_credentials(base)
                sess = base

        except NoCredentialsError as exc:
            raise AuthError(
                "No AWS credentials found. Configure via environment variables, "
                "~/.aws/credentials, or an IAM instance profile."
            ) from exc
        except ClientError as exc:
            raise AuthError(f"AWS authentication failed: {exc}") from exc

        self._sessions[pool_key] = sess
        return sess

    def client(self, service: str, **session_kwargs) -> Any:
        """Convenience wrapper: ``self.session(**kwargs).client(service)``."""
        return self.session(**session_kwargs).client(service)

    def whoami(self, **session_kwargs) -> dict[str, str]:
        """Return the caller's STS identity."""
        sts = self.client("sts", **session_kwargs)
        return sts.get_caller_identity()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _validate_credentials(self, sess: boto3.Session) -> None:
        sts = sess.client("sts")
        identity = sts.get_caller_identity()
        log.info(
            "authenticated",
            extra={"account": identity["Account"], "arn": identity["Arn"]},
        )

    def _assume_role(
        self,
        base: boto3.Session,
        role_arn: str,
        region: str,
    ) -> boto3.Session:
        cache_key = f"role_creds:{role_arn}"
        cached = self._cache.get(cache_key)

        if cached is not None and cached["wall_exp"] - time.time() > _REFRESH_BUFFER_S:
            log.debug("using cached role creds", extra={"role_arn": role_arn})
            creds = cached["creds"]
        else:
            session_name = f"awscli-{int(time.time())}"
            log.info(
                "assuming role",
                extra={"role_arn": role_arn, "session_name": session_name},
            )
            sts = base.client("sts")
            try:
                resp = sts.assume_role(
                    RoleArn=role_arn,
                    RoleSessionName=session_name,
                    DurationSeconds=3600,
                )
            except ClientError as exc:
                raise AuthError(f"Cannot assume role {role_arn!r}: {exc}") from exc

            creds = resp["Credentials"]
            wall_exp = creds["Expiration"].timestamp()
            ttl = max(60, int(wall_exp - time.time() - _REFRESH_BUFFER_S))
            self._cache.set(
                cache_key,
                {"creds": creds, "wall_exp": wall_exp},
                ttl=ttl,
            )
            log.info(
                "role assumed",
                extra={"role_arn": role_arn, "expires": str(creds["Expiration"])},
            )

        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region,
        )
