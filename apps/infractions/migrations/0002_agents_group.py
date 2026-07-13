from django.db import migrations


def create_agents_group(apps, schema_editor):
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
