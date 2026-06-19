# Patotinha

Patotinha e um sistema web para organizar grupos recorrentes, chamados de patotas. Um usuario pode criar uma patota, compartilhar um codigo de convite com outras pessoas e acompanhar quem vai, quem nao vai e quem ainda nao respondeu para a proxima reuniao da patota.

## Funcionalidades

- Cadastro e login de usuarios
- Criacao de patotas recorrentes
- Codigo privado de convite para entrada de membros
- Entrada em patotas por codigo
- Confirmacao de presenca com tres estados:
  - Vou
  - Nao vou
  - Sem resposta
- Painel da patota com lista de membros e status de presenca
- Dashboard com patotas criadas e patotas em que o usuario participa

## Tecnologias

- Python
- Flask
- SQLAlchemy
- Flask-WTF
- SQLite
- HTML
- CSS

## Como Rodar o Projeto

### Pre-requisitos

Tenha instalado:

- Python 3.12 ou superior
- Poetry

### Instalacao

Entre na pasta do projeto:

```bash
cd patotinha
cd johnny
```

Instale as dependencias:

```bash
poetry install
```

Rode a aplicacao:

```bash
poetry run flask --app app run
```

Acesse no navegador:

```txt
http://127.0.0.1:5000/
```

## Como Usar

1. Crie uma conta.
2. Faca login.
3. Crie uma patota informando nome, rotina e descricao.
4. Compartilhe o codigo da patota com outras pessoas.
5. Outro usuario entra usando o codigo.
6. Cada membro marca se vai ou nao vai.
7. O dono acompanha as respostas no painel da patota.

## Estrutura do Projeto

```txt
johnny/
├── app.py
├── pyproject.toml
├── poetry.lock
├── README.md
├── instance/
│   └── patotinha.db
├── static/
│   └── css/
│       └── style.css
└── templates/
    ├── home.html
    ├── login.html
    ├── registro.html
    ├── patotas.html
    ├── explorar.html
    └── patota_detalhe.html
```

## Observacoes

O banco de dados usado e SQLite e fica dentro da pasta `instance/`. Em ambiente de producao, a chave secreta do Flask deve ser configurada por variavel de ambiente.

## Proximas Melhorias

- Permitir o dono remover membros
- Criar historico de encontros anteriores
- Resetar respostas para uma nova semana
- Editar dados da patota
- Melhorar permissoes administrativas
