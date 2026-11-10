export APP_QBITLEAP_QORD_MAIN_API_URL="http://qbitleap-qord-main_transport_1:8080/v1/"
export APP_QBITLEAP_QORD_MAIN_API_USER="reader"
export APP_QBITLEAP_QORD_MAIN_API_TOKEN="$(derive_entropy "${app_entropy_identifier}-read-api")"
export APP_QBITLEAP_QORD_MAIN_LOCAL_TOKEN="$(derive_entropy "${app_entropy_identifier}-local-rpc")"
