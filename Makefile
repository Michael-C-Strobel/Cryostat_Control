server-compose-interactive:
	docker-compose --compatibility build
	docker-compose --compatibility -f docker-compose.yml up