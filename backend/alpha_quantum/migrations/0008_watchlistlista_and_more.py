from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        # Asegura que el modelo de usuario esté disponible (sea el que sea)
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('alpha_quantum', '0007_alter_watchlist_options_cartera_creada_and_more'),
    ]

    operations = [
        # 1) Crear el contenedor de listas
        migrations.CreateModel(
            name='WatchlistLista',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=120)),
                ('descripcion', models.CharField(max_length=255, blank=True, null=True)),
                # null=True para evitar prompts si ya hay filas existentes al migrar
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='watchlists',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={'ordering': ['titulo']},
        ),

        # 2) Constraint: único por usuario + título
        migrations.AddConstraint(
            model_name='watchlistlista',
            constraint=models.UniqueConstraint(
                fields=('user', 'titulo'),
                name='uq_watchlistlista_user_titulo'
            ),
        ),

        # 3) Añadir FK 'lista' a Watchlist (nullable para evitar default erróneo)
        migrations.AddField(
            model_name='watchlist',
            name='lista',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='items',
                to='alpha_quantum.watchlistlista',
                null=True,   # luego lo haremos obligatorio en una migración de backfill
                blank=True,
            ),
        ),

        # 4) Índice + constraint en Watchlist (user, lista, ticker)
        migrations.AddIndex(
            model_name='watchlist',
            index=models.Index(
                fields=['user', 'lista', 'ticker'],
                name='idx_wl_user_lista_ticker'
            ),
        ),
        migrations.AddConstraint(
            model_name='watchlist',
            constraint=models.UniqueConstraint(
                fields=('user', 'lista', 'ticker'),
                name='uq_watchlist_user_lista_ticker'
            ),
        ),
    ]
