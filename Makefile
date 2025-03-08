build-keithley:
	docker-compose up -d --build keithley-2400-backend

server-compose-interactive:
	docker-compose --compatibility build
	docker-compose --compatibility -f docker-compose.yml up
