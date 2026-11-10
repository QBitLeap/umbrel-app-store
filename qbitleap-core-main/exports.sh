export APP_QBITLEAP_CORE_MAIN_READ_URL="http://qbitleap-core-main_core_1:8081/"
export APP_QBITLEAP_CORE_MAIN_READ_USER="reader"
export APP_QBITLEAP_CORE_MAIN_READ_TOKEN="$(derive_entropy "${app_entropy_identifier}-read-rpc")"
export APP_QBITLEAP_CORE_MAIN_UI_TOKEN="$(derive_entropy "${app_entropy_identifier}-status-ui")"
