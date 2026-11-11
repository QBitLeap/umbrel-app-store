export APP_QBITLEAP_PINS_TESTNET4_API_URL="http://qbitleap-pins-testnet4_transport_1:8080/v1/"
export APP_QBITLEAP_PINS_TESTNET4_API_USER="reader"
export APP_QBITLEAP_PINS_TESTNET4_API_TOKEN="$(derive_entropy "app-qbitleap-pins-testnet4-seed-read-api")"
export APP_QBITLEAP_PINS_TESTNET4_LOCAL_TOKEN="$(derive_entropy "app-qbitleap-pins-testnet4-seed-local-rpc")"
