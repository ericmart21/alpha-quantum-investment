from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alpha_quantum', '0009_backfill_watchlist_listas'),
    ]

    operations = [
        migrations.AddField(
            model_name='watchlist',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='watchlist',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
