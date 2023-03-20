#!/bin/bash

set -e

cd ~ || exit

sudo apt update && sudo apt install redis-server libcups2-dev

pip install frappe-bench

git clone https://github.com/frappe/frappe --branch version-14 --depth 1
bench init --skip-assets --frappe-path ~/frappe --python "$(which python)" frappe-bench

mysql --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL character_set_server = 'utf8mb4'"
mysql --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'"

mysql --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE USER 'test_frappe'@'localhost' IDENTIFIED BY 'test_frappe'"
mysql --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE DATABASE test_frappe"
mysql --host 127.0.0.1 --port 3306 -u root -proot -e "GRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'localhost'"

mysql --host 127.0.0.1 --port 3306 -u root -proot -e "FLUSH PRIVILEGES"

cd ~/frappe-bench || exit

sed -i 's/watch:/# watch:/g' Procfile
sed -i 's/schedule:/# schedule:/g' Procfile
sed -i 's/socketio:/# socketio:/g' Procfile
sed -i 's/redis_socketio:/# redis_socketio:/g' Procfile

bench get-app payments --branch version-14
bench get-app erpnext --branch version-14
bench get-app klarna_kosma_integration "${GITHUB_WORKSPACE}"

bench new-site --db-root-password root --admin-password admin test_site --install-app erpnext
bench --site test_site install-app klarna_kosma_integration
bench setup requirements --dev
