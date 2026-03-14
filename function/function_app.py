"""
Azure Function: IoT Hub → Cosmos DB
Wird automatisch ausgelöst wenn eine Nachricht im IoT Hub ankommt.
"""

import json
import logging
import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="IoTHubTrigger")
@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="",          # Leer lassen — wird aus IoT Hub Connection übernommen
    connection="IOT_HUB_CONNECTION",
    consumer_group="$Default",
    cardinality="one",
)
@app.cosmos_db_output(
    arg_name="outputDoc",
    database_name="iotdb",
    container_name="measurements",
    connection="COSMOS_DB_CONNECTION",
    create_if_not_exists=True,
    partition_key="/deviceId",
)
def iot_hub_trigger(event: func.EventHubEvent, outputDoc: func.Out[func.Document]):
    """Liest IoT-Nachricht und schreibt sie in Cosmos DB."""

    try:
        # Nachricht parsen
        raw_body = event.get_body().decode("utf-8")
        data = json.loads(raw_body)

        logging.info(f"📨 Nachricht empfangen von: {data.get('deviceId', 'unbekannt')}")

        # Dokument für Cosmos DB aufbereiten
        document = {
            "id": f"{data['deviceId']}-{data['timestamp']}",
            "deviceId": data["deviceId"],
            "timestamp": data["timestamp"],
            "temperature": data["temperature"],
            "humidity": data["humidity"],
            "pressure": data["pressure"],
        }

        outputDoc.set(func.Document.from_dict(document))
        logging.info(f"✅ Gespeichert: Temp={data['temperature']}°C")

    except Exception as e:
        logging.error(f"❌ Fehler beim Verarbeiten: {str(e)}")
        raise


@app.route(route="measurements", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@app.cosmos_db_input(
    arg_name="docs",
    database_name="iotdb",
    container_name="measurements",
    connection="COSMOS_DB_CONNECTION",
    sql_query="SELECT TOP 100 * FROM c ORDER BY c.timestamp DESC",
)
def get_measurements(req: func.HttpRequest, docs: func.DocumentList) -> func.HttpResponse:
    """REST-Endpoint: Gibt die letzten 100 Messwerte zurück (für das Dashboard)."""

    items = [doc.to_dict() for doc in docs]

    return func.HttpResponse(
        body=json.dumps(items),
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},  # CORS für React-Dashboard
    )
