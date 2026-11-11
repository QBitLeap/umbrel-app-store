export APP_QBITLEAP_PINS_MAIN_API_URL="http://qbitleap-pins-main_transport_1:8080/v1/"
export APP_QBITLEAP_PINS_MAIN_API_USER="reader"
export APP_QBITLEAP_PINS_MAIN_API_TOKEN="$(derive_entropy "app-qbitleap-pins-main-seed-read-api")"
export APP_QBITLEAP_PINS_MAIN_LOCAL_TOKEN="$(derive_entropy "app-qbitleap-pins-main-seed-local-rpc")"
