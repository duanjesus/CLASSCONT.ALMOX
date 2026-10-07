from django.db import migrations

# O save()/delete() do model protegem o ORM; este trigger protege a tabela:
# nem um UPDATE/DELETE em SQL direto (ou QuerySet.update) altera o kardex.
CRIAR = """
CREATE FUNCTION estoque_kardex_imutavel() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'O kardex é imutável: % em estoque_movimentacao não é permitido. Corrija com um lançamento de ajuste.', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER kardex_imutavel
    BEFORE UPDATE OR DELETE ON estoque_movimentacao
    FOR EACH ROW EXECUTE FUNCTION estoque_kardex_imutavel();
"""

REMOVER = """
DROP TRIGGER kardex_imutavel ON estoque_movimentacao;
DROP FUNCTION estoque_kardex_imutavel();
"""


class Migration(migrations.Migration):
    dependencies = [("estoque", "0002_initial")]

    operations = [migrations.RunSQL(CRIAR, reverse_sql=REMOVER)]
