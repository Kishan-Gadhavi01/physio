<!-- Tech Badges -->

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.10-blue" />
  <img src="https://img.shields.io/badge/React-18-61dafb" />
  <img src="https://img.shields.io/badge/PyTorch-2.1-ee4c2c" />
  <img src="https://img.shields.io/badge/CUDA-12.1-76b900" />
  <img src="https://img.shields.io/badge/MMCV-2.1.0-orange" />
  <img src="https://img.shields.io/badge/MMPose-Live%203D%20Pose%20Estimation-purple" />
  <img src="https://img.shields.io/badge/WebSockets-Real--time-green" />
</p>

---


# 🧠 PhysioTrack — AI‑Powered Physiotherapy Motion Analysis Platform

### **A full‑stack AI/ML  project showcasing computer vision, biomechanics, real‑time systems, and frontend engineering**

This project demonstrates end‑to‑end expertise across:

### 🚀 **Machine Learning & Deep Learning**

* LSTM‑based exercise classification (10 physiotherapy movements)
* LSTM‑based repetition detection model
* Feature extraction for biomechanical time‑series
* Custom scalers, preprocessing, and post‑processing pipelines

### 📸 **Computer Vision & 3D Pose Estimation**

* Live webcam 3D human pose inference using **OpenMMLab MMPose**
* MMCV/Torch/CUDA compatibility engineering
* 3D → anatomical angle transformation (23‑joint kinematic model)

### 🦿 **Biomechanics & Kinematics**

* Custom inverse‑kinematics pipeline for: neck, waist, shoulders, hips, knees, elbows
* Angle smoothing, filtering, and rep signal extraction

### 🖥️ **Backend Engineering (Python)**

* WebSocket server for real‑time 3D pose streams
* REST API for classification, rep detection, and analytics
* Plotly‑based clinical analysis reports

### 🎨 **Frontend Engineering (React)**

* Real‑time 3D skeleton viewer
* Physiotherapy dashboard (angles, reps, exercise timeline)
* Full playback/analysis workflow

### 🛠️ **DevOps & Environment Engineering**

* CUDA/PyTorch/MMCV compatibility resolution
* Conda environment management
* Production‑ready local backend/frontend structure


---

# 🌟 Overview — What PhysioTrack Does

PhysioTrack is a **web‑based physiotherapy platform** that allows clinicians to:

* Capture **live 3D human motion** using a normal webcam
* View **real‑time joint angles** (23‑angle biomechanical model)
* Auto‑detect **exercise type** using an LSTM classifier
* Count **repetitions** using AI and peak detection
* Analyze recorded sessions using Plotly dashboards
* Track patient progress and recovery patterns

This system functions as a **clinical‑grade AI motion‑analysis tool**, built entirely from scratch.

---

# 🧩 System Architecture (High‑Level)

```
Front End (React + Vite + Three.js)
│   ├── Live 3D Skeleton Viewer
│   ├── Angle Dashboard
│   ├── Exercise Timeline
│   └── Rep Visualizer
│
Backend (Python)
│   ├── Live Pose Stream (WebSocket)
│   ├── Kinematics Engine (23 DOF)
│   ├── Movement Classifier (LSTM)
│   ├── Repetition Detector (LSTM)
│   └── Analytics API (REST)
│
MMPose (OpenMMLab)
    └── 3D Human Pose Estimation Engine
```

---

# 📂 Project Structure

```
.
├── aws/                    # Deployment notes
├── environment.yml         # Conda base env
├── experiments/            # Training, experiments, notebooks
├── local/
│   ├── backend/            # Main backend (WS + REST)
│   └── frontend/           # Full React dashboard
```

---

# 🛠️ Key Technologies Used

### **Computer Vision:**

* OpenMMLab MMPose (3D human pose estimation)
* MMCV
* TorchVision

### **AI / Machine Learning:**

* PyTorch (LSTM models)
* Time‑series feature engineering
* Biomechanical angle extraction
* Scikit‑learn (scalers)

### **Full‑Stack Engineering:**

* Python FastAPI‑style API
* WebSockets for real‑time CV streaming
* React + Three.js + Plotly
* Vite build system

### **DevOps & System Skills:**

* CUDA version alignment
* PyTorch/MMCV binary debugging
* Correcting NumPy ABI compatibility
* Environment reproducibility

This project showcases deep capability across **AI, CV, biomechanics, backend systems, and modern frontend engineering**.

---

# ⚙️ CRITICAL — Environment Setup (For Real‑Time 3D Streaming)

This system uses a fragile combination of CV + CUDA libs.
The following procedure is **mandatory** to avoid binary errors.

### Version Targets:

* **NumPy 1.26.4**
* **PyTorch 2.1.0 (CUDA 12.1)**
* **MMCV 2.1.0 (cu121 → torch2.1)**

---

## 🔹 Phase 1 — Clone & Install

```
conda activate proj_2

git clone https://github.com/open-mmlab/mmpose.git
cd mmpose
pip install -r requirements.txt
```

## 🔹 Phase 2 — Stabilize Dependencies

```
pip uninstall numpy opencv-python xtcocotools mmcv -y
pip install numpy==1.26.4

conda install pytorch=2.1.0 torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y

pip install xtcocotools
pip install opencv-python==4.9.0.80

pip install mmcv==2.1.0 -f https://download.openmmlab.com/mmcv/dist/cu121/torch2.1/index.html

pip install -v -e .
```

This resolves:

* dtype‑size NumPy error
* MMCV CUDA linker errors
* Torch/MMCV ABI mismatch

---

# ▶️ Running the App

## Start Backend

```
cd local/backend
python webcam.py   # WebSocket 8000
python api.py      # REST API 8001
```

## Start Frontend

```
cd local/frontend
npm install
npm run dev
```

Frontend available at:

```
http://localhost:5173
```

---

# 📈 Outputs & Features
### 🔹 Live 3D Pose Tracking
![3D Pose](./assets/3d.png)

### 🔹 Physiotherapy Analytics Dashboard
![Dashboard](./assets/dashboard.png)

* Live 3D skeleton (17 keypoints → 23 biomechanical angles)
* Exercise classification timeline
* Rep detection & peak visualization
* Time‑series angle plots
* Downloadable session results

