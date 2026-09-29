# Safe Street – Road Damage Detection and Reporting System

Safe Street is a web-based road damage detection and reporting system designed to help users report road problems such as potholes, cracks, and other road-surface damage.

The application combines image-based road damage detection with location-based reporting, public road-damage visualization, user authentication, administrator management, and report status tracking.

## Repository Description

Safe Street is a Flask-based web application that combines YOLO-based image detection, MongoDB-backed report management, user authentication, public road-damage reporting, interactive maps, and administrator tools.

The repository includes packaged YOLO model weights, application services, frontend templates, static assets, utility scripts, and documentation required to run the application locally.

## Project Visuals

![Project overview](docs/assets/overview-hero.svg)

![Inference pipeline](docs/assets/pipeline-flow.svg)

![Model comparison](docs/assets/model-comparison.svg)

![Repository layout](docs/assets/repo-layout.svg)

![Release readiness](docs/assets/release-readiness.svg)

## Highlights

- Flask-based web application for road-damage reporting and image-based detection
- YOLO-based image detection for identifying road damage
- Two packaged YOLO models for local inference
- User registration and authentication
- Separate administrator authentication and management
- Image-based road damage reporting
- Automatic damage type and priority detection
- Location and description support for reports
- Public dashboard and interactive road-damage map
- User-specific My Reports section
- Administrator dashboard and report management
- Report status workflow: Submitted → Under Review → Verified
- Community verification of reported road problems
- Damage hotspot visualization
- MongoDB database integration
- Responsive web interface
- Utility scripts for inference and annotation inspection
- Sample outputs and archived evaluation assets included for reference

## Included Models

### Model 1

- File: `models/m1-best.pt`
- Type: custom-trained YOLOv8m
- Size: 52.0 MB
- Best suited for the main app workflow and broad anomaly detection

### Model 2

- File: `models/m2-road-damage.pt`
- Type: pre-trained YOLOv8s road-damage model
- Size: 89.6 MB
- Useful for comparison runs and alternate road-damage labeling

## Performance Snapshot

Model 1 test-set summary from the archived evaluation results:

| Metric | Value |
| --- | --- |
| Precision | 0.736 |
| Recall | 0.740 |
| mAP@0.5 | 0.745 |
| mAP@0.5:0.95 | 0.448 |

Primary classes covered by the main application:

- Heavy-Vehicle
- Light-Vehicle
- Pedestrian
- Crack
- Crack-Severe
- Pothole
- Speed-Bump

## How the Application Works

1. A user creates an account and logs in.
2. The user opens the road damage reporting page.
3. The user uploads an image of the road problem.
4. The system analyzes the image using the YOLO-based detection pipeline.
5. The detected damage type and priority are displayed.
6. The user adds the road location and description.
7. The user reviews and submits the report.
8. The report is stored in MongoDB.
9. Submitted reports become available through the public dashboard and map.
10. Administrators can review reports and update their official status.

## Report Status Workflow

Safe Street uses the following official report workflow:

**Submitted → Under Review → Verified**

Administrator actions control the official report status.

Community verification is separate from the official administrator status and does not directly change the official status of a report.

## User Features

### Authentication
- User registration
- User login
- User logout
- User profile
- User-specific report history

### Road Damage Reporting
- Image upload
- YOLO-based image detection
- Damage type detection
- Priority/severity information
- Location selection
- Road description
- Report submission
- Report confirmation

### Public Features
- Public dashboard
- Public road-damage map
- Public report details
- Explore road problems
- Damage hotspot visualization
- Community verification

Users can view submitted road-damage reports publicly without logging in. Authentication is required when submitting a new report.

## Administrator Features

- Separate administrator login
- Administrator dashboard
- View all submitted reports
- Search and filter reports
- High-priority report management
- Report verification
- Official report status management
- Analytics
- Damage hotspot information
- Administrative report details

Administrator access is protected separately from normal user accounts.

## Image Reporting

Every submitted road-damage report requires a valid image as evidence.

Supported image formats include:

- JPG
- JPEG
- PNG
- WEBP

Video uploads are not part of the current road-damage reporting workflow.

The image is processed through the existing YOLO-based detection pipeline to identify road damage and determine the corresponding report information.

## Location Support

Reports can contain location information such as:

- Latitude
- Longitude
- Address/location description

Location information is used for displaying reports on the public map and for road-damage hotspot visualization.

## Technology Stack

### Frontend

- HTML
- CSS
- JavaScript
- Jinja2 Templates
- Interactive Maps

### Backend

- Python
- Flask

### Machine Learning

- YOLOv8
- PyTorch

### Database

- MongoDB
- PyMongo

### Development

- Git
- GitHub
- VS Code / Cursor

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Sowmya-726/Safe-Street.git
cd Safe-Street
