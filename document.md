# Road Anomaly Detection Project Documentation

## 1. Project Overview

This project is a computer-vision-based road inspection system built to detect visible road anomalies such as cracks and potholes from images, videos, and live camera feeds.

The main user-facing application is a Streamlit web app that lets a user:

- upload a road image and get annotated defect detection results
- upload a road video and download a processed annotated video
- use a live camera feed for near real-time road-surface inspection
- generate a PDF report for image-based inspections
- compare predictions from two YOLO-based detection models

The goal of the project is to make road-condition inspection easier, faster, and more consistent by using deep learning instead of only manual review.

## 2. What Problem This Project Solves

Manual road inspection is slow, expensive, and difficult to scale. This project helps by automatically identifying visible defects from road-surface visuals.

It is useful for:

- road maintenance teams
- smart city systems
- highway inspection workflows
- municipal engineering departments
- researchers working on road-surface monitoring
- proof-of-concept demos for AI-powered infrastructure inspection

## 3. Main Features

- Streamlit-based interface for easy testing
- image, video, and live camera support
- two-model detection workflow
- defect-focused detection filtering
- adjustable confidence thresholds
- annotated visual output
- downloadable processed video
- downloadable PDF report for image inspections
- clean dark UI for focused review

## 4. Current Project Structure

The repository is now organized around the Streamlit runtime.

```text
road-anomaly-detection-main/
├── main.py
├── README.md
├── document.md
├── requirements.txt
├── packages.txt
├── models/
│   ├── m1-best.pt
│   └── m2-road-damage.pt
├── docs/
│   ├── setup.md
│   └── web-interface.md
├── scripts/
│   ├── run.py
│   ├── run2model.py
│   └── visualize_annotations_data.py
├── notebooks/
│   └── train.ipynb
├── archive/
│   ├── training-results/
│   ├── evaluation-results/
│   ├── sample-output/
│   ├── flask-interface/
│   └── base-model-checkpoints/
├── .streamlit/
│   └── config.toml
└── .venv/
```

## 5. Important Files Explained

### `main.py`

This is the main Streamlit application. It handles:

- loading both YOLO models
- image inference
- video inference
- live webcam processing
- visual annotation
- PDF report generation
- session-state-based output management

### `models/m1-best.pt`

This is the custom-trained primary model used by the project.

It is best suited for the custom road-anomaly classes used in this project.

### `models/m2-road-damage.pt`

This is the second model used for comparison and broader defect coverage.

### `requirements.txt`

Contains the Python dependencies needed to run the project.

### `docs/setup.md`

Contains local setup steps for installing dependencies and launching the app.

### `scripts/run.py`

A helper script for single-model testing outside Streamlit.

### `scripts/run2model.py`

A helper script for dual-model testing outside Streamlit.

### `archive/`

Stores older experiments, evaluation outputs, non-primary interfaces, and sample outputs so the main project root stays clean.

## 6. Technology Stack

- Python
- Streamlit
- Ultralytics YOLO
- OpenCV
- NumPy
- Supervision
- streamlit-webrtc
- ReportLab

## 7. Models Used in This Project

## Model 1: Custom YOLOv8m

Primary purpose:

- detect road anomalies using the project’s custom training setup

Expected role in the app:

- main detection model for road-surface defects

Configured path:

- `./models/m1-best.pt`

Defect class IDs used in the app:

- `3, 4, 5, 6`

Default confidence:

- `0.35`

Fallback confidence:

- `0.15`

## Model 2: Secondary YOLO model

Primary purpose:

- provide secondary predictions and broader support for crack and pothole patterns

Configured path:

- `./models/m2-road-damage.pt`

Defect class IDs used in the app:

- `0, 1, 2, 3`

Default confidence:

- `0.40`

Fallback confidence:

- `0.18`

## 8. How the Detection Pipeline Works

The high-level processing flow is:

1. The user chooses an input source.
2. The app loads one or both selected YOLO models.
3. The app applies inference on the incoming image or video frame.
4. The app filters for road-defect classes.
5. Bounding boxes and labels are drawn on the frame.
6. The output is shown in the Streamlit interface.
7. For image mode, a PDF report can be downloaded.
8. For video mode, a processed video can be downloaded.

For difficult images, the app has a fallback confidence mechanism. If no detections are found at the normal threshold, it retries with a lower defect-only threshold.

## 9. Supported Input Modes

### A. Image Mode

Use this when:

- you want to inspect a single road image
- you want a quick visual review
- you need a PDF report

What happens:

- the image is uploaded
- defects are detected
- the image is annotated
- the app summarizes findings
- a PDF report becomes available for download

### B. Video Mode

Use this when:

- you want to inspect dashcam footage
- you want to process recorded road survey videos
- you want an annotated video output

What happens:

- the uploaded video is temporarily saved
- frames are read one by one
- each frame is processed through the selected models
- an output video is written
- the processed video is available for download

### C. Live Camera Mode

Use this when:

- you want near real-time road monitoring
- you want to test from a webcam or a connected camera
- you want a live inspection demonstration

What happens:

- the camera feed is captured in real time
- frames are resized and processed
- live annotations are displayed in the Streamlit interface

## 10. How To Run The Project

## Step 1: Open the project folder

```powershell
cd C:\Users\Hariom kumar\Desktop\road-anomaly-detection-main
```

## Step 2: Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

## Step 3: Install dependencies

```powershell
pip install -r requirements.txt
```

## Step 4: Launch the Streamlit app

```powershell
python -m streamlit run main.py
```

## Step 5: Open the local app in your browser

Streamlit usually opens automatically. If not, open the local URL shown in the terminal, typically:

```text
http://localhost:8501
```

## 11. How To Use The App

### Using image mode

1. Start the app.
2. Select the image input option.
3. Upload a road image.
4. Keep one model or both models selected.
5. Adjust confidence if needed.
6. Review the annotated image.
7. Read the defect summary.
8. Download the generated PDF report.

### Using video mode

1. Start the app.
2. Select video input.
3. Upload a road video.
4. Wait for processing to finish.
5. Review the status.
6. Download the processed video.

### Using live mode

1. Start the app.
2. Select the live camera option.
3. Allow camera access in the browser if prompted.
4. Point the camera toward the road surface.
5. Watch detections appear on the frames.

## 12. Real-Time Usage in Practical Scenarios

This project can be used in real-time or near real-time depending on the camera quality, system resources, and model performance.

### Example 1: Dashcam-based road inspection

A vehicle fitted with a dashboard camera can capture road footage while driving. The live camera mode or uploaded recorded footage can be used to detect:

- potholes
- severe cracks
- surface damage patterns

Practical use:

- a city maintenance team can review damaged road sections after a route survey

### Example 2: Municipal road survey vehicle

A government or contractor vehicle can collect road videos daily or weekly. The project can process those videos and help teams identify segments needing repair.

Practical use:

- prioritize which roads should be repaired first

### Example 3: Campus or industrial site road monitoring

Private campuses, factories, or logistics yards can monitor internal roads using fixed or mobile cameras.

Practical use:

- detect road wear before it becomes a safety issue

### Example 4: Research and demonstration

Universities or AI researchers can use this project as a base system for:

- road-defect detection experiments
- model comparison
- dataset evaluation
- smart transportation demos

## 13. Real-Time Example Workflow

Here is a simple real-world example.

Scenario:

- A road-inspection team mounts a camera on a survey vehicle.
- The vehicle drives through a city road segment.
- The camera records road footage.
- The footage is processed through this project.
- The app marks potholes and cracks.
- Engineers use the processed results to prepare maintenance work.

Expected result:

- faster issue discovery
- more consistent inspection records
- easier visual reporting for decision-makers

## 14. Example User Cases

### Example A: Single image inspection

Input:

- one image of a damaged road

Expected output:

- annotated image with labels
- list of detected defects
- confidence values
- downloadable PDF report

### Example B: Recorded video inspection

Input:

- a dashcam video of a road

Expected output:

- annotated MP4 video with visible detections frame by frame

### Example C: Live camera testing

Input:

- webcam stream focused on a road or test surface

Expected output:

- live annotated frames in the browser

## 15. Example Commands

### Run the app

```powershell
python -m streamlit run main.py
```

### Run the single-model helper script

```powershell
python scripts\run.py
```

### Run the dual-model helper script

```powershell
python scripts\run2model.py
```

## 16. Output Produced By The Project

Depending on the mode, the project can generate:

- annotated image previews
- detection summary tables
- confidence-based findings
- PDF reports
- annotated processed videos
- live visual overlays on camera frames

## 17. PDF Report Contents

For image inspections, the PDF report generated by the app includes:

- source image name
- generation time
- number of findings
- overall status
- interpretation summary
- model-wise detection details
- annotated image snapshot

## 18. Performance Notes

Performance depends on:

- CPU or GPU availability
- camera resolution
- frame size
- selected model count
- browser performance for live streaming

Using both models gives broader review coverage, but it can be slower than using one model.

## 19. Limitations

This project is useful, but it still has practical limitations.

- detection quality depends on image clarity
- poor lighting can reduce accuracy
- motion blur can affect video predictions
- very small defects may be missed
- water, shadows, mud, and occlusions can confuse detection
- live inference speed depends heavily on hardware
- this is an assistance tool, not a replacement for engineering judgment

## 20. Recommended Best Practices

- use clear road-facing images or videos
- avoid very dark or blurry inputs
- test with both models for better comparison
- lower the confidence threshold slightly for harder cases
- use recorded road-survey footage for repeatable evaluation
- keep model files in the `models/` directory
- keep the app entrypoint as `main.py`

## 21. Troubleshooting

### Problem: `streamlit` command not found

Use:

```powershell
python -m streamlit run main.py
```

### Problem: model file not found

Check that these files exist:

- `models/m1-best.pt`
- `models/m2-road-damage.pt`

### Problem: webcam does not start

Check:

- browser camera permission
- webcam availability
- whether another app is already using the camera

### Problem: slow video processing

Try:

- reducing resolution
- using only one model
- testing on a smaller clip first
- using a machine with GPU support

## 22. Who Can Use This Project

- students
- AI/ML researchers
- civic-tech developers
- municipal engineering teams
- smart city prototype builders
- infrastructure monitoring teams

## 23. Future Improvements

This project can be extended further with:

- road-segment severity scoring
- GPS-tagged defect logging
- batch processing for multiple videos
- database-backed inspection history
- map-based visualization
- mobile-device deployment
- automatic maintenance prioritization
- cloud deployment for centralized inspection

## 24. Summary

This project is a practical road anomaly detection system built around a Streamlit application and YOLO models. It supports image, video, and live camera input, gives annotated results, and helps turn raw road visuals into more useful inspection outputs.

If you want to demo road-defect detection, test a road image quickly, process a survey video, or build a more advanced road-monitoring workflow on top of this base, this project is a strong starting point.
