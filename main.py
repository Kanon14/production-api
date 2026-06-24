from app.config import get_settings


def main():
    settings = get_settings()

    print(f"Environment: {settings.app_env}")
    print(f"Primary model: {settings.primary_model}")
    print(f"Rate limit: {settings.rate_limit}")
    print(f"Cache TTL: {settings.cache_ttl_seconds}s")
    print(f"Max retries: {settings.max_retries}")
    print(f"Is production: {settings.is_production}")
    print("Config loaded successfully!")


if __name__ == "__main__":
    main()
