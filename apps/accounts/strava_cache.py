from django.core.cache import cache


STRAVA_RAW_PROFILE_KEY = "strava_raw_profile:{user_id}"
PROFILE_PIC_CACHE_KEY = "profile_pic:{user_id}"

# Persist indefinitely — refreshed via webhook or re-auth.
STRAVA_RAW_PROFILE_TTL = None


def get_strava_raw_profile(user_id):
    """Return the Strava athlete profile dict from Redis, or None."""
    return cache.get(STRAVA_RAW_PROFILE_KEY.format(user_id=user_id))


def set_strava_raw_profile(user_id, profile_data):
    """
    Store the Strava athlete profile dict in Redis and
    invalidate the derived profile-pic URL cache so the
    next read picks up any change immediately.
    """
    cache.set(
        STRAVA_RAW_PROFILE_KEY.format(user_id=user_id),
        profile_data,
        timeout=STRAVA_RAW_PROFILE_TTL,
    )
    # Invalidate the derived pic-url so serializer re-derives it.
    cache.delete(PROFILE_PIC_CACHE_KEY.format(user_id=user_id))


def delete_strava_raw_profile(user_id):
    """Remove both the raw profile and the derived pic-url from Redis."""
    cache.delete(STRAVA_RAW_PROFILE_KEY.format(user_id=user_id))
    cache.delete(PROFILE_PIC_CACHE_KEY.format(user_id=user_id))
