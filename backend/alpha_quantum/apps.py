from django.apps import AppConfig

class AlphaQuantumConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'alpha_quantum'

    def ready(self):
        import alpha_quantum.signals
