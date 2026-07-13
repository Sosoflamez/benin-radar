from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_supervisors_group(apps, schema_editor):
    # Même contrainte que 0002_agents_group : les permissions "verify_infraction"/
    # "validate_infraction" (déclarées sur Meta.permissions d'Infraction) ne sont
    # pas encore créées à ce stade de la migration.
    create_permissions(global_apps.get_app_config("infractions"), verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    # Un agent peut désormais faire passer une infraction detectee -> verifiee.
    agents = Group.objects.get(name="Agents")
    verify_permission = Permission.objects.get(codename="verify_infraction")
    agents.permissions.add(verify_permission)

    # Seul un superviseur valide ou rejette une infraction vérifiée.
    supervisors, _ = Group.objects.get_or_create(name="Superviseurs")
    codenames = [
        "view_plate_data",
        "view_evidence",
        "view_infraction",
        "verify_infraction",
        "validate_infraction",
    ]
    permissions = Permission.objects.filter(codename__in=codenames)
    supervisors.permissions.set(permissions)


def remove_supervisors_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    Group.objects.filter(name="Superviseurs").delete()
    agents = Group.objects.filter(name="Agents").first()
    if agents is not None:
        agents.permissions.remove(Permission.objects.get(codename="verify_infraction"))


class Migration(migrations.Migration):
    dependencies = [
        ("infractions", "0003_evidence_access_log_and_permissions"),
    ]

    operations = [
        migrations.RunPython(create_supervisors_group, remove_supervisors_group),
    ]
