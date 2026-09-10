# OTel messaging span attribute keys used to derive observed queue relationships (spec §32).
MESSAGING_SYSTEM = "messaging.system"
MESSAGING_DESTINATION_NAME = "messaging.destination.name"
MESSAGING_DESTINATION_TEMPLATE = "messaging.destination.template"
MESSAGING_OPERATION_NAME = "messaging.operation.name"
MESSAGING_OPERATION_TYPE = "messaging.operation.type"
# v0.4.1 I2 (docs/specifications/0.4.1/i2-messaging-semantic-guards.md §8-9) - read only as
# destination-kind safety evidence by the messaging guards, never as an operation-recognition
# signal and never as a substitute for MESSAGING_DESTINATION_NAME.
MESSAGING_DESTINATION_KIND = "messaging.destination_kind"
