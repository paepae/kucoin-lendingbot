DISCLAIMER: This application has been published for educational purposes. The author is not responsible for any errors or damages, or for the results obtained from the use of the application. Use at your own risk.

---

A bot performs crypto lending on KuCoin via KuCoin REST API (https://docs.kucoin.cc/)

- Run as Google Cloud Functions
- Read configurations from Google Cloud Firestore

---

Stack
- Python 3.8
- Google Cloud Firestore
- Google Cloud Functions

---

Google Cloud setup

Install Google Cloud SDK
https://cloud.google.com/sdk/docs/quickstart

Create and download a service account key and save as `gcloud_user.json`.
https://cloud.google.com/iam/docs/creating-managing-service-account-keys

To deploy to Google Cloud Functions, you need to setup environment parameters using a template file `gcloud_env.template.sh` and save as `gcloud_env.sh`.

---

Install dependencies
```
pip install -r requirements.txt
```

Run locally
```
./run.sh
```

Call to get current status
```
curl --location --request POST 'http://127.0.0.1:18080/' \
--header 'Content-Type: application/json' \
--data-raw '{ "get_lending_status": 1 }'
```

Call to execute lending function
```
curl --location --request POST 'http://127.0.0.1:18080/?execute=1' \
--header 'Content-Type: application/json' \
--data-raw '{ "get_lending_status": 1 }'
```

Deploy to Google Cloud Functions
```
./deploy.sh
```
