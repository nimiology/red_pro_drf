from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Squad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('athletes', models.ManyToManyField(blank=True, related_name='squads', to='accounts.user')),
                ('coach', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_squads', to='accounts.user')),
            ],
        ),
    ]
