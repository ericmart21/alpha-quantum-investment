from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('alpha_quantum', '0010_add_watchlist_timestamps'),
    ]

    operations = [
        # Elimina cualquier unique_together antiguo (user, ticker)
        migrations.AlterUniqueTogether(
            name='watchlist',
            unique_together=set(),
        ),
    ]
