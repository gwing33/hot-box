import json


def publish_readings(readings):
    """
    Publish a list of sensor readings to MQTT.

    readings: list of (timestamp, device_name, sensor_id, sensor_name, temp_c)

    Topic format: sensors/{device_name}/{sensor_name}/{sensor_id}/ds18b20
    Payload:      {"temperature_c": <float>}

    This maps directly into the existing Node-RED generic sensor flow
    which writes to InfluxDB under measurement=ds18b20.
    """
    try:
        from secrets import HOT_BOX_ID, MQTT_HOST, MQTT_PASSWORD, MQTT_PORT, MQTT_USER
    except ImportError:
        print("MQTT: credentials not found in secrets.py, skipping")
        return False

    try:
        from umqtt.simple import MQTTClient
    except ImportError:
        print("MQTT: umqtt.simple not available")
        return False

    client = MQTTClient(
        client_id=f"hot-box-{HOT_BOX_ID}",
        server=MQTT_HOST,
        port=int(MQTT_PORT),
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=30,
    )

    try:
        client.connect()
        for _, device_name, sensor_id, sensor_name, temp_c in readings:
            topic = f"sensors/{device_name}/{sensor_name}/{sensor_id}/ds18b20"
            payload = json.dumps({"temperature_c": temp_c})
            client.publish(topic.encode(), payload.encode(), qos=1)
        client.disconnect()
        print(f"MQTT: published {len(readings)} readings")
        return True
    except Exception as e:
        print(f"MQTT: publish failed: {e}")
        try:
            client.disconnect()
        except Exception:
            pass
        return False
