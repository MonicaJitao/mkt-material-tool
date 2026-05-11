from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "mkt-material-tool"
    DEBUG: bool = False

    # SQLite 路径（相对于启动目录，即 backend/）
    DATABASE_URL: str = "sqlite:///./workspace/mkt_material.db"

    # 工作区根目录（相对或绝对路径）
    WORKSPACE_DIR: str = "workspace"

    # Tuzi Banana 生图 —— Agent B 使用
    TUZI_API_KEY: str = ""
    TUZI_API_BASE: str = "https://api.tu-zi.com"
    TUZI_IMAGE_MODEL: str = "gemini-3-pro-image-preview-2k-async"

    # Anthropic / Claude HTML 生成 —— Agent C 使用
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_MAX_TOKENS: int = 12000

    # DeepSeek（Anthropic 兼容接口）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/anthropic"


settings = Settings()
