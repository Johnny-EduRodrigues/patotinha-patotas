import os
import secrets

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_wtf import FlaskForm
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import EmailField, PasswordField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length

app = Flask(__name__)
app.config["SECRET_KEY"] = "troque-essa-chave-em-producao"

os.makedirs(app.instance_path, exist_ok=True)
engine = create_engine(
    f"sqlite:///{os.path.join(app.instance_path, 'patotinha.db')}",
    echo=False,
)
SessionLocal = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)
    usuario = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)

    patotas = relationship("Patota", back_populates="criador")
    participacoes = relationship("MembroPatota", back_populates="usuario")


class Patota(Base):
    __tablename__ = "patotas"

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=False)
    quando_acontece = Column(String(120), nullable=True)
    codigo_convite = Column(String(20), unique=True, nullable=False)
    criador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    criador = relationship("Usuario", back_populates="patotas")
    membros = relationship("MembroPatota", back_populates="patota")


class MembroPatota(Base):
    __tablename__ = "membros_patota"
    __table_args__ = (UniqueConstraint("usuario_id", "patota_id"),)

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    patota_id = Column(Integer, ForeignKey("patotas.id"), nullable=False)
    presenca_confirmada = Column(Boolean, nullable=False, default=False)
    resposta_presenca = Column(String(20), nullable=True)

    usuario = relationship("Usuario", back_populates="participacoes")
    patota = relationship("Patota", back_populates="membros")


class RegistroUsuario(FlaskForm):
    usuario = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=80)])
    email = EmailField("Email", validators=[DataRequired()])
    senha = PasswordField("Senha", validators=[DataRequired(), Length(min=6)])
    confirmar_senha = PasswordField(
        "Confirmar senha",
        validators=[DataRequired(), EqualTo("senha", message="As senhas precisam ser iguais.")],
    )
    submit = SubmitField("Criar conta")


class LoginUsuario(FlaskForm):
    usuario = StringField("Usuario", validators=[DataRequired()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    submit = SubmitField("Entrar")


class PatotaForm(FlaskForm):
    nome = StringField("Nome da patota", validators=[DataRequired(), Length(min=3, max=100)])
    quando_acontece = StringField(
        "Quando acontece",
        validators=[DataRequired(), Length(min=3, max=120)],
    )
    descricao = TextAreaField("Descricao", validators=[DataRequired(), Length(min=10)])
    submit = SubmitField("Criar patota")


class EntrarCodigoForm(FlaskForm):
    codigo = StringField("Codigo de convite", validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField("Entrar na patota")


def gerar_codigo_convite(db):
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    while True:
        codigo = "PATO-" + "".join(secrets.choice(alfabeto) for _ in range(6))
        existe = db.scalar(select(Patota).where(Patota.codigo_convite == codigo))
        if not existe:
            return codigo


def normalizar_codigo_convite(codigo):
    codigo_limpo = "".join(codigo.strip().upper().split())
    if codigo_limpo.startswith("PATO") and not codigo_limpo.startswith("PATO-"):
        codigo_limpo = f"PATO-{codigo_limpo[4:]}"
    return codigo_limpo


def status_presenca(participacao):
    if participacao.resposta_presenca in {"vai", "nao_vai"}:
        return participacao.resposta_presenca
    if participacao.presenca_confirmada:
        return "vai"
    return "sem_resposta"


def resumo_presencas(membros):
    resumo = {"vai": 0, "nao_vai": 0, "sem_resposta": 0, "total": len(membros)}
    for membro in membros:
        resumo[status_presenca(membro)] += 1
    return resumo


def preparar_banco():
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        colunas_patotas = [
            coluna[1]
            for coluna in conn.exec_driver_sql("PRAGMA table_info(patotas)").fetchall()
        ]
        if "codigo_convite" not in colunas_patotas:
            conn.exec_driver_sql("ALTER TABLE patotas ADD COLUMN codigo_convite VARCHAR(20)")
        if "quando_acontece" not in colunas_patotas:
            conn.exec_driver_sql("ALTER TABLE patotas ADD COLUMN quando_acontece VARCHAR(120)")

        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_patotas_codigo_convite "
            "ON patotas (codigo_convite)"
        )

        colunas_membros = [
            coluna[1]
            for coluna in conn.exec_driver_sql("PRAGMA table_info(membros_patota)").fetchall()
        ]
        if "presenca_confirmada" not in colunas_membros:
            conn.exec_driver_sql(
                "ALTER TABLE membros_patota "
                "ADD COLUMN presenca_confirmada BOOLEAN NOT NULL DEFAULT 0"
            )
        if "resposta_presenca" not in colunas_membros:
            conn.exec_driver_sql("ALTER TABLE membros_patota ADD COLUMN resposta_presenca VARCHAR(20)")
            conn.exec_driver_sql(
                "UPDATE membros_patota SET resposta_presenca = 'vai' "
                "WHERE presenca_confirmada = 1"
            )

        conn.exec_driver_sql(
            "DELETE FROM membros_patota "
            "WHERE id NOT IN ("
            "SELECT MIN(id) FROM membros_patota GROUP BY usuario_id, patota_id"
            ")"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_membros_usuario_patota "
            "ON membros_patota (usuario_id, patota_id)"
        )

    db = SessionLocal()
    patotas_sem_codigo = db.scalars(
        select(Patota).where(Patota.codigo_convite.is_(None))
    ).all()
    for patota in patotas_sem_codigo:
        patota.codigo_convite = gerar_codigo_convite(db)

    db.commit()
    SessionLocal.remove()


preparar_banco()


@app.teardown_appcontext
def remove_session(exception=None):
    SessionLocal.remove()


def usuario_logado():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None

    db = SessionLocal()
    return db.get(Usuario, usuario_id)


@app.route("/")
def home():
    return render_template("home.html", usuario=usuario_logado())


@app.route("/registro", methods=["GET", "POST"])
def registro():
    form = RegistroUsuario()

    if form.validate_on_submit():
        db = SessionLocal()
        usuario_existente = db.scalar(
            select(Usuario).where(
                (Usuario.usuario == form.usuario.data) | (Usuario.email == form.email.data)
            )
        )

        if usuario_existente:
            flash("Ja existe uma conta com esse usuário ou email.", "erro")
            return render_template("registro.html", form=form)

        novo_usuario = Usuario(
            usuario=form.usuario.data,
            email=form.email.data,
            senha_hash=generate_password_hash(form.senha.data),
        )
        db.add(novo_usuario)
        db.commit()

        flash("Conta criada com sucesso. Agora e so entrar.", "sucesso")
        return redirect(url_for("login"))

    return render_template("registro.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginUsuario()

    if form.validate_on_submit():
        db = SessionLocal()
        usuario = db.scalar(select(Usuario).where(Usuario.usuario == form.usuario.data))

        if not usuario or not check_password_hash(usuario.senha_hash, form.senha.data):
            flash("Usuario ou senha invalidos.", "erro")
            return render_template("login.html", form=form)

        session["usuario_id"] = usuario.id
        flash(f"Bem-vindo, {usuario.usuario}!", "sucesso")
        return redirect(url_for("patotas"))

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("Voce saiu da sua conta.", "sucesso")
    return redirect(url_for("home"))


@app.route("/patotas", methods=["GET", "POST"])
def patotas():
    usuario = usuario_logado()
    if not usuario:
        flash("Entre na sua conta para acessar suas patotas.", "erro")
        return redirect(url_for("login"))

    form = PatotaForm()
    db = SessionLocal()
    busca = request.args.get("q", "").strip()

    if form.validate_on_submit():
        patota = Patota(
            nome=form.nome.data,
            descricao=form.descricao.data,
            quando_acontece=form.quando_acontece.data.strip(),
            codigo_convite=gerar_codigo_convite(db),
            criador_id=usuario.id,
        )
        db.add(patota)
        db.commit()
        flash("Patota criada com sucesso.", "sucesso")
        return redirect(url_for("patotas"))

    consulta = select(Patota).where(Patota.criador_id == usuario.id)
    if busca:
        termo = f"%{busca}%"
        consulta = consulta.where(
            (Patota.nome.ilike(termo)) | (Patota.descricao.ilike(termo))
        )

    lista_patotas = db.scalars(consulta.order_by(Patota.id.desc())).all()
    participacoes = db.scalars(
        select(MembroPatota)
        .where(MembroPatota.usuario_id == usuario.id)
        .join(Patota)
        .order_by(Patota.id.desc())
    ).all()
    presencas_por_patota = {
        patota.id: resumo_presencas(patota.membros)
        for patota in lista_patotas
    }
    total_patotas = len(usuario.patotas)
    return render_template(
        "patotas.html",
        busca=busca,
        form=form,
        participacoes=participacoes,
        patotas=lista_patotas,
        presencas_por_patota=presencas_por_patota,
        total_patotas=total_patotas,
        total_participando=len(participacoes),
        usuario=usuario,
    )


@app.route("/explorar", methods=["GET", "POST"])
def explorar():
    usuario = usuario_logado()
    if not usuario:
        flash("Entre na sua conta para usar um codigo de convite.", "erro")
        return redirect(url_for("login"))

    db = SessionLocal()
    form = EntrarCodigoForm()

    if form.validate_on_submit():
        codigo = normalizar_codigo_convite(form.codigo.data)
        patota = db.scalar(select(Patota).where(Patota.codigo_convite == codigo))

        if not patota:
            flash("Codigo de convite invalido.", "erro")
            return render_template("explorar.html", form=form, usuario=usuario)

        if patota.criador_id == usuario.id:
            flash("Voce ja e o dono dessa patota.", "erro")
            return redirect(url_for("patotas"))

        participacao = db.scalar(
            select(MembroPatota).where(
                MembroPatota.usuario_id == usuario.id,
                MembroPatota.patota_id == patota.id,
            )
        )
        if participacao:
            flash("Voce ja participa dessa patota.", "sucesso")
            return redirect(url_for("patotas"))

        db.add(MembroPatota(usuario_id=usuario.id, patota_id=patota.id))
        db.commit()
        flash(f"Voce entrou na patota {patota.nome}.", "sucesso")
        return redirect(url_for("patotas"))

    return render_template("explorar.html", form=form, usuario=usuario)


@app.route("/patotas/<int:patota_id>/entrar", methods=["POST"])
def entrar_patota(patota_id):
    flash("Para entrar em uma patota, use o codigo de convite.", "erro")
    return redirect(url_for("explorar"))


@app.route("/patotas/<int:patota_id>")
def painel_patota(patota_id):
    usuario = usuario_logado()
    if not usuario:
        flash("Entre na sua conta para acessar o painel da patota.", "erro")
        return redirect(url_for("login"))

    db = SessionLocal()
    patota = db.get(Patota, patota_id)
    if not patota:
        flash("Patota nao encontrada.", "erro")
        return redirect(url_for("patotas"))

    participacao_usuario = db.scalar(
        select(MembroPatota).where(
            MembroPatota.usuario_id == usuario.id,
            MembroPatota.patota_id == patota.id,
        )
    )
    eh_dono = patota.criador_id == usuario.id

    if not eh_dono and not participacao_usuario:
        flash("Voce precisa participar dessa patota para ver o painel.", "erro")
        return redirect(url_for("patotas"))

    membros = sorted(patota.membros, key=lambda membro: membro.usuario.usuario.lower())
    return render_template(
        "patota_detalhe.html",
        eh_dono=eh_dono,
        membros=membros,
        patota=patota,
        resumo=resumo_presencas(membros),
        status_presenca=status_presenca,
        usuario=usuario,
    )


@app.route("/patotas/<int:patota_id>/presenca", methods=["POST"])
def atualizar_presenca(patota_id):
    usuario = usuario_logado()
    if not usuario:
        flash("Entre na sua conta para confirmar presenca.", "erro")
        return redirect(url_for("login"))

    db = SessionLocal()
    participacao = db.scalar(
        select(MembroPatota).where(
            MembroPatota.usuario_id == usuario.id,
            MembroPatota.patota_id == patota_id,
        )
    )

    if not participacao:
        flash("Voce precisa participar da patota para confirmar presenca.", "erro")
        return redirect(url_for("patotas"))

    resposta = request.form.get("presenca")
    if resposta == "1":
        resposta = "vai"
    elif resposta == "0":
        resposta = "sem_resposta"

    if resposta not in {"vai", "nao_vai", "sem_resposta"}:
        flash("Resposta de presenca invalida.", "erro")
        return redirect(request.referrer or url_for("patotas"))

    participacao.resposta_presenca = None if resposta == "sem_resposta" else resposta
    participacao.presenca_confirmada = resposta == "vai"
    db.commit()

    if resposta == "vai":
        flash(f"Presenca confirmada na proxima patota de {participacao.patota.nome}.", "sucesso")
    elif resposta == "nao_vai":
        flash(f"Voce marcou que nao vai na proxima patota de {participacao.patota.nome}.", "sucesso")
    else:
        flash(f"Resposta removida da proxima patota de {participacao.patota.nome}.", "sucesso")

    return redirect(request.referrer or url_for("patotas"))


@app.route("/patotas/<int:patota_id>/sair", methods=["POST"])
def sair_patota(patota_id):
    usuario = usuario_logado()
    if not usuario:
        flash("Entre na sua conta para sair de uma patota.", "erro")
        return redirect(url_for("login"))

    db = SessionLocal()
    participacao = db.scalar(
        select(MembroPatota).where(
            MembroPatota.usuario_id == usuario.id,
            MembroPatota.patota_id == patota_id,
        )
    )

    if participacao:
        db.delete(participacao)
        db.commit()
        flash("Voce saiu da patota.", "sucesso")
    else:
        flash("Voce nao participa dessa patota.", "erro")

    return redirect(request.referrer or url_for("patotas"))


if __name__ == "__main__":
    app.run(debug=True)
