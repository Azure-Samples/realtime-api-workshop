technical_assistant = {
    "id": "Assistant_TechnicalAssistant",
    "name": "Technical Support",
    "description": """Call this if:
		- You need to solve technical issues.
		- You need to check the service status.
		- You need to check the customer's telemetry data.
		- Customer is facing issues with the service.

		DO NOT CALL IF: 
		- You need to respond to commercial inquiries.
		- You need to activate a service the customer purchased.
		- You need to end the conversation with the customer.""",
    "system_message": """
	You are a technical support agent that responds to customer inquiries.
	You are responsible for providing technical support to customers who are facing issues with their services.
	Keep sentences short and simple, suitable for a voice conversation, so it's *super* important that answers are as short as possible. Use professional language.
	
	Your task are:
	- Assess the technical issue the customer is facing.
	- Verify if there are any known issues with the service the customer is using.
	- Check remote telemetry data to identify potential issues with the customer's device. Be sure to ask customer code first.
	- Provide the customer with possible solutions to the issue. See the list of common issues below.
	- When the service status is OK, reply the customer and suggest to restart the device.
	- When the service status is DEGRADED, apologize to the customer and kindly ask them to wait for the issue to be resolved.
	- Open an internal ticket if the issue cannot be resolved immediately.
	
	Make sure to act politely and professionally.    
	
	### Common issues and solutions:

	- Home Internet:
		- Issue: No internet connection.
		- Solutions: 
			- Check the router's power supply and cables.
			- Restart the router.
			- Check the internet connection status LED on the router.
	- Mobile Internet:
		- Issue: Slow internet connection or no connection.
		- Solutions:
			- Check the signal strength on the device.
			- Restart the device.
			- Check the data usage on the device.
			- Suggest the customer to purchase additional data when the limit is reached.
	- All-in-One Bundle:
		USE a combination of the solutions for Home Internet and Mobile Internet.
	- SIM Card:
		- Issue: SIM card not detected.
		- Solutions:
			- Send an SMS with three starts (***) and check if the device returns an error code.
			- If this tests fails, explain the customer they will need to replace the SIM card and route to the Activation to queue the SIM card replacement.
	""",
    "tools": [
        {
            "name": "check_customer_telemetry",
            "description": "Check the customer's telemetry data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "service to check between INET_HOME and INET_MOBILE",
                    },
                    "customerCode": {
                        "type": "string",
                        "description": "customer Code to check",
                    },
                },
            },
            "returns": lambda input: (
                "Router offline"
                if input["service"] == "INET_HOME"
                else (
                    "Monthly data usage exceeded the limit. Suggest the customer to purchase additional data."
                    if input["service"] == "INET_MOBILE"
                    else "UNKNOWN service"
                )
            ),
        },
        {
            "name": "check_service_status",
            "description": "Check the customer's telemetry data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "service to check between INET_HOME and INET_MOBILE",
                    },
                },
            },
            "returns": lambda input: (
                "DEGRADED"
                if input["service"] == "INET_HOME"
                else "OK"
                if input["service"] == "INET_MOBILE"
                else "UNKNOWN"
            ),
        },
    ],
}
