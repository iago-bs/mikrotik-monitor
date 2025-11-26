### Configuração Mikrotik

Abrir Mikrotik na máquina virtual importando a imagem
Login padrão: admin
Senha padrão: (deixe vazia)
Depois será solicitado para criar uma nova senha.

Após isso, utilize os seguintes comandos:

Para habilitar o SNMP 

/snmp set enable=yes

Para definir a community

(Normalmente ele já gera por padrão o "public")

/snmp community add name=public

Para ver os status do SNMP
/snmp print

Para verificar o IP do Mikrotik
/ip address print

Para verificar as interfaces
/interface print

Para deixar rodando o monitoramento e comparar dados
/interface monitor-traffic "nome da interface"<br><br>


### Configuração de Dependências

Na pasta raiz do projeto executar:

python -m venv venv

venv\Scripts\activate

python -m pip install -r backend/requirements.txt<br><br>


### Para Testar

Na pasta backend, adicionar as informações ao arquivo .env.example e renomear para .env
Configurar:

IP do Mikrotik

SNMP community

Depois execute:

python app.py


E acesse no navegador:

http://localhost:5000/
