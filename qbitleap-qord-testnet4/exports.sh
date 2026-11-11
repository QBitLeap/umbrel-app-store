export APP_QBITLEAP_QORD_TESTNET4_API_URL="http://qbitleap-qord-testnet4_transport_1:8080/v1/"
export APP_QBITLEAP_QORD_TESTNET4_API_USER="reader"
export APP_QBITLEAP_QORD_TESTNET4_API_TOKEN="$(derive_entropy "app-qbitleap-qord-testnet4-seed-read-api")"
export APP_QBITLEAP_QORD_TESTNET4_LOCAL_TOKEN="$(derive_entropy "app-qbitleap-qord-testnet4-seed-local-rpc")"
