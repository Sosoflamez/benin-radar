from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_agents_group(apps, schema_editor):
    # Le signal post_migrate (qui crée les permissions "view_x"/"change_x" auto-générées)
    # n'est émis qu'une fois toutes les migrations appliquées : à ce stade de la migration,
    # les permissions des apps anpr/infractions n'existent pas encore. On les force ici.
    for app_label in ("anpr", "infractions"):
        create_permissions(global_apps.get_app_config(app_label), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group, _ = Group.objects.get_or_create(name="Agents")
    codenames = [
        "view_plate_data",
        "view_evidence",
        "view_infraction",
        "change_infraction",
    ]
    permissions = Permission.objects.filter(codename__in=codenames)
    group.permissions.set(permissions)


def remove_agents_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Agents").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("infractions", "0001_initial"),
        ("anpr", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_agents_group, remove_agents_group),
    ]
