from collections import defaultdict
import firebase_admin
from firebase_admin import credentials, db, firestore
import neurokit2 as nk
from datetime import datetime
from dotenv import load_dotenv
import os
import numpy as np

# Load environment variables
load_dotenv(dotenv_path='.env')
FIREBASE_CREDENTIALS = os.getenv('FIREBASE_CREDENTIALS_PATH')
FIREBASE_DATABASE_URL = os.getenv('FIREBASE_DATABASE_URL')

# Validate environment variables
if not FIREBASE_CREDENTIALS or not FIREBASE_DATABASE_URL:
    raise ValueError("Missing Firebase credentials or database URL in .env file")

if not os.path.isfile(FIREBASE_CREDENTIALS):
    raise FileNotFoundError(f"Firebase credentials file '{FIREBASE_CREDENTIALS}' not found.")

# Initialize Firebase Admin SDK
cred = credentials.Certificate(FIREBASE_CREDENTIALS)
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DATABASE_URL})

# Initialize Firestore
firestore_db = firestore.client()

# Reference to the main node in Realtime Database
data_ref = db.reference('Emotibit')

# Global buffers for data storage
buffer_EDA = []
buffer_PPG = []

# Number of events to trigger processing
EVENT_THRESHOLD = 10

# Firestore document storage
firestore_doc = {}

# Listener for data changes
def listener(event):
    try:
        firestore_doc['device_id'] = event.path.split('/')[1]
        
        # Get the data from the event
        data = event.data
        if not data or 'PPG_array' not in data or 'EDA_array' not in data:
            print(f"Invalid data received: {data}")
            return

        # Calculate means using NumPy
        mean_ppg = np.mean(data.get('PPG_array', []))
        mean_eda = np.mean(data.get('EDA_array', []))

        # Prepare Firestore document
        timestamp = data.get('Timestamp')
        if not timestamp:
            print("No timestamp found in the data.")
            return

        firebase_doc = {
            'device_id': firestore_doc['device_id'],
            'EDA_mean': mean_eda,
            'PPG_mean': mean_ppg,
            'timestamp': timestamp
        }

        # Save processed data to Firestore
        doc_ref = firestore_db.collection("realtimedata").document(str(timestamp))
        doc_ref.set(firebase_doc)
        print(f"Document saved: {firebase_doc}")

        # Add received data to buffers
        eda_array = data.get('EDA_array', [])
        ppg_array = data.get('PPG_array', [])

        buffer_EDA.append(eda_array)
        buffer_PPG.append(ppg_array)

        print(f"Buffered PPG count: {len(buffer_PPG)}")

        # Process buffer when the threshold is reached
        if len(buffer_PPG) >= EVENT_THRESHOLD:
            process_buffer(buffer_PPG, buffer_EDA)

    except Exception as e:
        print(f"Error processing event: {e}")

def process_buffer(buffer_PPG, buffer_EDA):
    try:
        # Flatten the buffers
        PPG = [item for sublist in buffer_PPG for item in sublist]
        EDA = [item for sublist in buffer_EDA for item in sublist]

        print('Processing data...')

        # Process signals using NeuroKit2
        ppg_elgendi = nk.ppg_clean(PPG, method='elgendi')
        eda_cleaned = nk.eda_clean(EDA, sampling_rate=100, method='neurokit')

        signal, _ = nk.ppg_process(ppg_elgendi, sampling_rate=100)

        # Convert processed data to Firestore-compatible format
        timestamp = datetime.now().isoformat()

        firestore_doc.update({
            'PPG_clean': ppg_elgendi.tolist(),
            'EDA_clean': eda_cleaned.tolist(),
            'HR': signal['PPG_Rate'].tolist(),
            'timestamp': timestamp
        })

        firestore_db.collection('preprocess').document(timestamp).set(firestore_doc)
        print('Processed data pushed to Firestore successfully.')

        # Clear buffers
        buffer_EDA.clear()
        buffer_PPG.clear()

    except Exception as e:
        print(f'Error processing data: {e}')

# Start listening for database changes
data_ref.listen(listener)
