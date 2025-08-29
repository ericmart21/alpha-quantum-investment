# backend/alpha_quantum/migrations/0009_backfill_watchlist_listas.py
from django.db import migrations

def forwards(apps, schema_editor):
    Watchlist = apps.get_model('alpha_quantum', 'Watchlist')
    WatchlistLista = apps.get_model('alpha_quantum', 'WatchlistLista')

    user_ids = (Watchlist.objects
                .filter(lista__isnull=True)
                .values_list('user_id', flat=True)
                .distinct())

    for uid in user_ids:
        lista, _ = WatchlistLista.objects.get_or_create(user_id=uid, titulo='Mi Watchlist')
        # importante: usar *_id en update
        Watchlist.objects.filter(user_id=uid, lista__isnull=True).update(lista_id=lista.id)

class Migration(migrations.Migration):

    dependencies = [
        ('alpha_quantum', '0008_watchlistlista_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
