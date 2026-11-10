export APP_QBITLEAP_CORE_TESTNET4_READ_URL="http://qbitleap-core-testnet4_core_1:8081/"
export APP_QBITLEAP_CORE_TESTNET4_READ_USER="reader"
export APP_QBITLEAP_CORE_TESTNET4_READ_TOKEN="$(derive_entropy "${app_entropy_identifier}-read-rpc")"
export APP_QBITLEAP_CORE_TESTNET4_UI_TOKEN="$(derive_entropy "${app_entropy_identifier}-status-ui")"
