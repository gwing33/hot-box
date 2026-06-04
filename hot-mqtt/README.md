# Hot MQTT Broker
Username: opuntia
Password: pricklypads1!

mosquitto_sub -L mqtts://opuntia:asdf1!@hot-mqtt.fly.dev:10000/# --cafile ./certs/rootCA.pem

mosquitto_sub -L 'mqtts://opuntia:pricklypads1!@hot-mqtt.fly.dev:10000/#' --cafile ./certs/rootCA.pem

mosquitto_pub -L 'mqtts://opuntia:pricklypads1!@hot-mqtt.fly.dev:10000/tests' --cafile certs/rootCA.pem  -l
