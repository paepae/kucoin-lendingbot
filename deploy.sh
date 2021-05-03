source gcloud_env.sh
gcloud functions deploy kucoin-lendingbot \
--region ${GCLOUD_FUNCTIONS_REGION} \
--runtime python38 \
--entry-point http_request \
--trigger-http --allow-unauthenticated \
--max-instances 1 \
--project ${GCLOUD_FUNCTIONS_PROJECT} \
--service-account ${GCLOUD_FUNCTIONS_SERVICE_ACCOUNT} \
