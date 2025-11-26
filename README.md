Configuração Mikrotik	
	Abrir Mikrotik na maquina virtual importando a imagem
	Login padrao admin
	Senha padrao pode deixar vazia 
	Vai pedir para criar uma nova senha
	Após utilize os seguintes comandos
	Para habilitar o snmp
		/snmp set enable=yes
	Para definir o community (Normalmente ele ja gera por padrão o "public")
		/snmp community add name=public
	Para ver os status do snmp 
		/snmp print
	Para verificar o ip do Mikrotik
		/ip adress print
	Para verificar as interfaces
		/interface print
	E se quiser deixar rodando o monitoramento para comparar os dados 
		/interface monitor-traffic "nome da interface"

Configuração de dependencias
	Na pasta raiz do projeto executar os seguintes comandos	
		python -m venv venv
		venv\Scripts\activate
		python -m pip install -r backend/requirements.txt

Para testar
	Na pasta backend adicionar as informações ao arquivo .env.example e mudar para .env
	O ip do mikrotik e o snmp_community
	Na pasta backend executar
		python app.py
	E acessar no navegador
	http://localhost:5000/
	
