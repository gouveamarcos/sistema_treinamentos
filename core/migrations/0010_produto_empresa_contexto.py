from django.db import migrations, models
import django.db.models.deletion


def vincular_produtos_a_empresas(apps, schema_editor):
    Empresa = apps.get_model("core", "Empresa")
    Produto = apps.get_model("core", "Produto")

    empresa_padrao = (
        Empresa.objects.filter(nome__iexact="Sem Parar").first()
        or Empresa.objects.order_by("id").first()
    )

    for produto in Produto.objects.all():
        empresa = (
            Empresa.objects.filter(cursos_disponiveis__produto=produto)
            .order_by("id")
            .first()
        )
        if empresa is None:
            empresa = empresa_padrao
        if empresa is None:
            continue
        produto.empresa = empresa
        produto.save(update_fields=["empresa"])


def limpar_empresa_produtos(apps, schema_editor):
    Produto = apps.get_model("core", "Produto")
    Produto.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_curso_empresas_disponiveis"),
    ]

    operations = [
        migrations.AddField(
            model_name="produto",
            name="empresa",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="produtos",
                to="core.empresa",
            ),
        ),
        migrations.RunPython(
            vincular_produtos_a_empresas,
            limpar_empresa_produtos,
        ),
        migrations.AlterField(
            model_name="produto",
            name="empresa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="produtos",
                to="core.empresa",
            ),
        ),
        migrations.AddConstraint(
            model_name="produto",
            constraint=models.UniqueConstraint(
                fields=("empresa", "nome"),
                name="produto_nome_unico_por_empresa",
            ),
        ),
        migrations.RemoveField(
            model_name="curso",
            name="empresas_disponiveis",
        ),
    ]
