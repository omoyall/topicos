class Config:
    SECRET_KEY = '83adfe5e1c804e48a5a65dca28f4d8c9'

class DevelopmentConfig(Config):
    DEBUG=True


config={
    'development': DevelopmentConfig
}

