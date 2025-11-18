import uvicorn
import io
import traceback
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import joblib
import sys

# --- Import Plotly ---
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
# ---------------------

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from scipy.signal import find_peaks
from collections import Counter

# --- FastAPI App Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1: REQUIRED FILES & CONSTANTS ---
CLASSIFIER_MODEL_PATH = 'movement_classifier_model.pth'
REP_DETECTOR_MODEL_PATH = 'rep_detector_model.pth'
SCALER_PATH = 'angle_scaler.joblib'
FPS = 100

# --- (Model class definitions) ---
class MovementClassifierLSTM(nn.Module):
    def __init__(self, input_size, hidden_size1, hidden_size2, num_classes, dropout_prob=0.5):
        super(MovementClassifierLSTM, self).__init__()
        self.lstm1 = nn.LSTM(input_size, hidden_size1, batch_first=True)
        self.dropout1 = nn.Dropout(dropout_prob)
        self.lstm2 = nn.LSTM(hidden_size1, hidden_size2, batch_first=True)
        self.dropout2 = nn.Dropout(dropout_prob)
        self.fc1 = nn.Linear(hidden_size2, 50)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(50, num_classes)
    def forward(self, x):
        out, _ = self.lstm1(x); out = self.dropout1(out)
        out, (hidden, _) = self.lstm2(out); out = self.dropout2(hidden.squeeze(0))
        out = self.fc1(out); out = self.relu(out); out = self.fc2(out)
        return out

class RepetitionDetector(nn.Module):
    def __init__(self, input_size=48, hidden_size=64, num_layers=2):
        super(RepetitionDetector, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_size * 2, 1)
    def forward(self, x):
        lstm_out, _ = self.lstm(x); out = self.fc(lstm_out)
        return out.squeeze(-1)

# --- (Constants) ---
CLASS_NAMES = [
    "Deep squat",                                  # m01
    "Hurdle step",                                 # m02
    "Inline lunge",                                # m03
    "Side lunge",                                  # m04
    "Sit to stand",                                # m05
    "Standing active straight leg raise",          # m06
    "Standing shoulder abduction",                 # m07
    "Standing shoulder extension",                 # m08
    "Standing shoulder internal-external rotation", # m09
    "Standing shoulder scaption"                   # m10
]
ANGLE_MAPPING = {
    "Head_Y": 0, "Head_X": 1, "Head_Z": 2, "Neck_Y": 9, "Neck_X": 10, "Neck_Z": 11,
    "Torso_Y": 21, "Torso_X": 22, "Torso_Z": 23, "Pelvis_Y": 30, "Pelvis_X": 31, "Pelvis_Z": 32,
    "L_Hip_Y": 39, "L_Hip_X": 40, "L_Hip_Z": 41, "L_Knee_Y": 51, "L_Knee_X": 52, "L_Knee_Z": 53,
    "L_Ankle_Y": 63, "L_Ankle_X": 64, "L_Ankle_Z": 65, "R_Hip_Y": 42, "R_Hip_X": 43, "R_Hip_Z": 44,
    "R_Knee_Y": 54, "R_Knee_X": 55, "R_Knee_Z": 56, "R_Ankle_Y": 66, "R_Ankle_X": 67, "R_Ankle_Z": 68,
    "L_Shoulder_Y": 81, "L_Shoulder_X": 82, "L_Shoulder_Z": 83, "L_Elbow_Y": 87, "L_Elbow_X": 88, "L_Elbow_Z": 89,
    "L_Wrist_Y": 99, "L_Wrist_X": 100, "L_Wrist_Z": 101, "R_Shoulder_Y": 84, "R_Shoulder_X": 85, "R_Shoulder_Z": 86,
    "R_Elbow_Y": 90, "R_Elbow_X": 91, "R_Elbow_Z": 92, "R_Wrist_Y": 102, "R_Wrist_X": 103, "R_Wrist_Z": 104,
}
if "L_Shoulder_Z" not in ANGLE_MAPPING: ANGLE_MAPPING["L_Shoulder_Z"] = 83
ANGLE_INDICES = list(ANGLE_MAPPING.values())
N_FEATURES = len(ANGLE_INDICES)
N_OUTPUTS = 10
WINDOW_SIZE = 60
STEP_CLS = 20
STEP_REP = 15

# --- (Helper function) ---
def calculate_rep_delays(peak_indices, fps=100):
    if len(peak_indices) < 2: return np.array([])
    return np.diff(peak_indices) / fps

# --- 2: Load Models and Scaler (On Startup) ---
try:
    print(f"Loading models and scaler... Expecting {N_FEATURES} features.")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model_cls = MovementClassifierLSTM(N_FEATURES, 80, 40, N_OUTPUTS)
    model_cls.load_state_dict(torch.load(CLASSIFIER_MODEL_PATH, map_location=device))
    model_cls.to(device); model_cls.eval()
    model_rep = RepetitionDetector(N_FEATURES, 64, 2)
    model_rep.load_state_dict(torch.load(REP_DETECTOR_MODEL_PATH, map_location=device))
    model_rep.to(device); model_rep.eval()
    scaler = joblib.load(SCALER_PATH)
    print("✅ All assets loaded.")
except FileNotFoundError as e:
    print(f"--- FATAL ERROR: FILE NOT FOUND: {e.filename} ---")
    sys.exit(1)
except Exception as e:
    print(f"--- FATAL ERROR: {e} ---")
    sys.exit(1)


# --- 3: The API Endpoint ---
@app.post("/analyze-session/")
async def analyze_session(file: UploadFile = File(...)):
    """
    Analyzes an 'angles.txt' file and returns Plotly graphs as HTML
    and a summary.
    """
    try:
        print(f"Received file: {file.filename}")
        contents = await file.read()
        
        # --- 4: Load and Preprocess Data ---
        try:
            new_data_full = np.loadtxt(io.BytesIO(contents), delimiter=",")
        except Exception:
            new_data_full = np.loadtxt(io.BytesIO(contents))
        if new_data_full.ndim == 1: new_data_full = new_data_full.reshape(1, -1)
        
        if new_data_full.shape[1] < max(ANGLE_INDICES):
             raise HTTPException(status_code=400, detail=f"File has only {new_data_full.shape[1]} columns, but model needs index {max(ANGLE_INDICES)}.")
        
        new_data = new_data_full[:, ANGLE_INDICES]
        scaled_data = scaler.transform(new_data)
        num_total_frames = len(scaled_data)
        print(f"Data ready: {num_total_frames} frames.")

        # --- 5: Run Classifier Pipeline ---
        print("Running exercise classification...")
        windows_cls = [scaled_data[i : i + WINDOW_SIZE] for i in range(0, num_total_frames - WINDOW_SIZE + 1, STEP_CLS)]
        if not windows_cls:
            raise HTTPException(status_code=400, detail="Data is too short to create any windows.")
        X_cls_tensor = torch.tensor(np.array(windows_cls), dtype=torch.float32).to(device)
        with torch.no_grad():
            out_cls = model_cls(X_cls_tensor); prob_cls = torch.softmax(out_cls, dim=1).cpu().numpy()
        pred_cls_indices = np.argmax(prob_cls, axis=1)
        pred_cls_names = [CLASS_NAMES[idx] for idx in pred_cls_indices]
        x_frames_cls = (np.arange(0, len(windows_cls)) * STEP_CLS)

        # --- 6: Run Repetition Detector Pipeline ---
        print("Running repetition detection...")
        windows_rep = [scaled_data[i : i + WINDOW_SIZE] for i in range(0, num_total_frames - WINDOW_SIZE + 1, STEP_REP)]
        X_rep_tensor = torch.tensor(np.array(windows_rep), dtype=torch.float32).to(device)
        with torch.no_grad():
            out_rep_seqs = model_rep(X_rep_tensor); prob_rep_seqs = torch.sigmoid(out_rep_seqs).cpu().numpy()
        full_rep_signal = np.zeros(num_total_frames, dtype=float)
        count_signal = np.zeros(num_total_frames, dtype=float)
        for i, seq in enumerate(prob_rep_seqs):
            start = i * STEP_REP; end = start + WINDOW_SIZE
            full_rep_signal[start:end] += seq
            count_signal[start:end] += 1
        final_rep_signal = np.divide(full_rep_signal, count_signal, out=np.zeros_like(full_rep_signal), where=count_signal!=0)
        x_frames_rep = np.arange(num_total_frames)
        peaks, _ = find_peaks(final_rep_signal, height=0.78, distance=90)
        
        # --- 7: Generate Plotly Figures (Your Python Code) ---
        print("Generating Plotly graphs...")
        
        # --- FIG 1: Classification & Reps ---
        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=('Exercise Classification', 'Repetition Peak Signal'))
        fig1.add_trace(go.Scatter(x=x_frames_cls, y=pred_cls_names, mode='lines', line=dict(shape='hv'), name='Predicted Exercise'), row=1, col=1)
        fig1.add_trace(go.Scatter(x=x_frames_rep, y=final_rep_signal, mode='lines', line=dict(color='green'), name='"Peak Hold" Probability'), row=2, col=1)
        fig1.add_trace(go.Scatter(x=peaks, y=final_rep_signal[peaks], mode='markers', marker=dict(color='red', size=10, symbol='x'), name=f'Detected Reps ({len(peaks)})'), row=2, col=1)
        fig1.update_layout(xaxis2_title='Frame Number', yaxis_title='Exercise', yaxis2_title='Probability', height=600, hovermode='x unified', margin=dict(t=40, b=40))
        
        # --- FIG 2: Rep Timing ---
        pred_delays = calculate_rep_delays(peaks, fps=FPS)
        fig2 = go.Figure()
        if pred_delays.size > 0:
            rep_intervals = [f"Rep {i}-{i+1}" for i in range(1, len(pred_delays) + 1)]
            fig2.add_trace(go.Scatter(
                name='Predicted Rep Delay',
                x=rep_intervals, 
                y=pred_delays, 
                mode='lines+markers',
                line=dict(color='red', dash='dash')
            ))
        fig2.update_layout(title_text="Repetition Timing: Time Between Reps", xaxis_title="Repetition Interval", yaxis_title="Time (seconds)", height=400, margin=dict(t=40, b=40))

        # --- Convert figures to HTML strings ---
        # THIS IS THE FIX: Set full_html=True and include_plotlyjs='cdn'
        # This creates a complete, standalone HTML document.
        html_fig1 = pio.to_html(fig1, full_html=True, include_plotlyjs='cdn')
        html_fig2 = pio.to_html(fig2, full_html=True, include_plotlyjs='cdn')

        # --- 8: Generate Summary ---
        print("Generating summary...")
        summary_lines = []
        if len(peaks) == 0:
            summary_lines.append("No repetitions were detected.")
        else:
            peak_exercises = []
            for peak_frame in peaks:
                chunk_index = np.searchsorted(x_frames_cls, peak_frame, side='right') - 1
                if chunk_index >= 0:
                    exercise_name = pred_cls_names[chunk_index]
                    peak_exercises.append(exercise_name)
            rep_counts = Counter(peak_exercises)
            for exercise, count in rep_counts.items():
                summary_lines.append(f"{exercise}: {count} reps")
            summary_lines.append(f"Total Reps Detected: {len(peaks)}")
            if pred_delays.size > 0:
                summary_lines.append(f"Average Time Between Reps: {np.mean(pred_delays):.2f} seconds")
        
        print("✅ Analysis complete.")

        # --- 9: Return JSON response with HTML and summary ---
        return {
            "fileName": file.filename,
            "plot_html_1": html_fig1, # Classification + Reps
            "plot_html_2": html_fig2, # Rep Timing
            "summary": summary_lines
        }

    except Exception as e:
        print(f"--- ERROR during analysis ---")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# --- 4: Main entry point ---
if __name__ == "__main__":
    print("[API] Starting analysis server on http://127.0.0.1:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001)