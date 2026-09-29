import os
from pathlib import Path
import tempfile
from collections import Counter
from datetime import datetime
from io import BytesIO

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode
import logging
import supervision as sv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(".ultralytics").resolve()))

from services.inference import (
    DEFAULT_CONF,
    LIVE_FEED_TARGET_WIDTH,
    MODEL_PATHS,
    analyze_frame,
    load_yolo_model as load_yolo_model_core,
    make_annotators,
    process_frame,
)

# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


if "processed_file_id" not in st.session_state:
    st.session_state.processed_file_id = None
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "output_file_path" not in st.session_state:
    st.session_state.output_file_path = None
if "output_file_name" not in st.session_state:
    st.session_state.output_file_name = None


def inject_premium_styles():
    st.markdown(
        """
        <style>
        :root {
            --bg: #111111;
            --panel: #171717;
            --panel-alt: #1d1d1d;
            --border: #303030;
            --text: #f5f5f5;
            --muted: #bdbdbd;
            --soft: #8d8d8d;
            --accent: #ffffff;
            --shadow: rgba(0, 0, 0, 0.28);
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        .main .block-container {
            max-width: 1320px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        [data-testid="collapsedControl"] {
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            display: none;
        }

        h1, h2, h3 {
            font-family: Georgia, "Times New Roman", serif;
            letter-spacing: 0.01em;
            color: var(--text);
        }

        p, li, label, div, span {
            color: var(--text);
        }

        a {
            color: var(--text) !important;
            text-decoration: none;
            border-bottom: 1px solid var(--border);
        }

        .shell {
            padding: 1.25rem 0 0.25rem;
        }

        .hero-card,
        .panel-card,
        .metric-card,
        .footer-card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 20px;
            box-shadow: 0 18px 40px var(--shadow);
        }

        .hero-card {
            padding: 2.1rem 2rem 1.8rem;
            margin-bottom: 1.4rem;
        }

        .hero-kicker {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.22em;
            font-size: 0.78rem;
            margin-bottom: 0.9rem;
        }

        .hero-title {
            font-size: 3rem;
            line-height: 1;
            margin: 0 0 0.9rem;
        }

        .hero-copy {
            max-width: 56rem;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.7;
            margin: 0;
        }

        .meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            margin-top: 1.25rem;
        }

        .meta-chip {
            border: 1px solid var(--border);
            background: var(--panel-alt);
            color: var(--text);
            border-radius: 999px;
            padding: 0.55rem 0.85rem;
            font-size: 0.82rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .section-label {
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.2em;
            font-size: 0.76rem;
            margin-bottom: 0.95rem;
        }

        .panel-card {
            padding: 1.35rem;
            height: 100%;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.9rem;
            margin-bottom: 1.2rem;
        }

        .metric-card {
            padding: 1rem 1rem 0.95rem;
        }

        .metric-label {
            color: var(--soft);
            text-transform: uppercase;
            letter-spacing: 0.15em;
            font-size: 0.72rem;
            margin-bottom: 0.55rem;
        }

        .metric-value {
            font-size: 1.3rem;
            font-weight: 600;
        }

        .panel-title {
            font-size: 1.35rem;
            margin: 0 0 0.3rem;
        }

        .panel-copy {
            color: var(--muted);
            line-height: 1.7;
            margin-bottom: 1rem;
        }

        .footer-card {
            margin-top: 1.25rem;
            padding: 1rem 1.2rem;
            color: var(--muted);
            font-size: 0.92rem;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: var(--panel-alt);
            border: 1px dashed #4a4a4a;
            border-radius: 18px;
            padding: 1rem;
        }

        [data-testid="stMarkdownContainer"] p {
            color: inherit;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] {
            width: 100%;
            border-radius: 14px;
            background: var(--accent);
            color: #111111;
            border: 1px solid var(--accent);
            min-height: 2.9rem;
            font-weight: 600;
            box-shadow: none;
        }

        .stRadio > div,
        .stCheckbox,
        .stSlider,
        .stFileUploader,
        .stAlert,
        .stProgress > div {
            color: var(--text);
        }

        [data-baseweb="input"],
        [data-baseweb="select"],
        [data-baseweb="textarea"] {
            background: var(--panel-alt);
        }

        [data-baseweb="slider"] > div > div {
            background: var(--accent);
        }

        [data-testid="stAlert"] {
            background: var(--panel-alt);
            border: 1px solid var(--border);
            border-radius: 16px;
            color: var(--text);
        }

        [data-testid="stImage"] img,
        video {
            border-radius: 18px;
            border: 1px solid var(--border);
        }

        @media (max-width: 980px) {
            .hero-title {
                font-size: 2.35rem;
            }

            .metric-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
        <div class="shell">
            <div class="hero-card">
                <div class="hero-kicker">Road Surface Inspection Suite</div>
                <h1 class="hero-title">Road Anomaly Detection</h1>
                <p class="hero-copy">
                    Premium monochrome workspace for image, video, and live-camera inspection.
                    Lightweight, static, and tuned for focused review across both YOLO models.
                </p>
                <div class="meta-row">
                    <span class="meta-chip">Charcoal Interface</span>
                    <span class="meta-chip">No Gradients</span>
                    <span class="meta-chip">No Animations</span>
                    <span class="meta-chip">Dual Model Workflow</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards():
    st.markdown(
        """
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-label">Modes</div>
                <div class="metric-value">Image / Video / Live</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Models</div>
                <div class="metric-value">YOLOv8m + YOLOv8s</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Output</div>
                <div class="metric-value">Annotated Detection Review</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel_intro(container, title: str, copy: str):
    container.markdown(
        f"""
        <div class="section-label">{title}</div>
        <h2 class="panel-title">{title}</h2>
        <p class="panel-copy">{copy}</p>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def load_yolo_model(path: str):
    model, names_map = load_yolo_model_core(path)
    if not model:
        st.error(f"Error loading model at {path}")
        return None, {}
    return model, names_map


def build_detection_insights(detection_summary):
    if not detection_summary:
        return [
            "No confident road defects were detected in this image with the current analysis settings.",
            "This usually means the road surface looks clean to the selected models, or the defect is too small, distant, or unclear in the uploaded image.",
            "For difficult cases, keep both models enabled and reduce the confidence sliders slightly to make the inspection more sensitive.",
        ]

    label_counts = Counter(item["label"] for item in detection_summary)
    model_counts = Counter(item["model"] for item in detection_summary)
    strongest = max(detection_summary, key=lambda item: item["confidence"])
    total_findings = len(detection_summary)
    dominant_label, dominant_count = label_counts.most_common(1)[0]
    avg_conf = sum(item["confidence"] for item in detection_summary) / total_findings

    insights = [
        f"The system found {total_findings} road issue(s) in this image.",
        f"The most frequent finding is {dominant_label.lower()}, appearing {dominant_count} time(s).",
        f"The strongest individual prediction is {strongest['label'].lower()} from {strongest['model']} with confidence {strongest['confidence']:.2f}.",
        f"Average confidence across all detections is {avg_conf:.2f}.",
    ]

    if len(model_counts) > 1:
        insights.append(
            "Both selected models contributed to the final review, which gives broader defect coverage across crack and pothole patterns."
        )
    else:
        only_model = next(iter(model_counts))
        insights.append(
            f"All reported findings came from {only_model}, so this result is based on a single-model interpretation."
        )

    return insights


def build_pdf_report(
    source_name: str,
    annotated_frame: np.ndarray,
    detection_summary,
    insight_lines,
):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=42,
        bottomMargin=42,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#111111"),
        spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#111111"),
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#222222"),
    )

    story = [
        Paragraph("Road Anomaly Detection Report", title_style),
        Paragraph(
            "A structured inspection summary generated from the uploaded road image.",
            body_style,
        ),
        Spacer(1, 0.2 * inch),
    ]

    metadata_rows = [
        ["Source Image", source_name],
        ["Generated On", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Detected Findings", str(len(detection_summary))],
        [
            "Overall Status",
            "Defects detected" if detection_summary else "No confident defects detected",
        ],
    ]
    metadata_table = Table(metadata_rows, colWidths=[1.8 * inch, 4.7 * inch])
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f2f2")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111111")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b7b7b7")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([metadata_table, Spacer(1, 0.22 * inch)])

    story.append(Paragraph("Interpretation", heading_style))
    for line in insight_lines:
        story.append(Paragraph(f"- {line}", body_style))
    story.append(Spacer(1, 0.22 * inch))

    if detection_summary:
        story.append(Paragraph("Detection Details", heading_style))
        detail_rows = [["Model", "Defect Type", "Confidence"]]
        for item in detection_summary:
            detail_rows.append(
                [
                    item["model"],
                    item["label"],
                    f"{item['confidence']:.2f}",
                ]
            )
        details_table = Table(detail_rows, colWidths=[1.8 * inch, 3.2 * inch, 1.2 * inch])
        details_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c6c6c6")),
                    ("PADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend([details_table, Spacer(1, 0.24 * inch)])

    story.append(Paragraph("Annotated Image", heading_style))
    success, encoded = cv2.imencode(".jpg", annotated_frame)
    if success:
        image_bytes = BytesIO(encoded.tobytes())
        report_image = ReportImage(image_bytes, width=6.5 * inch, height=3.9 * inch)
        report_image.hAlign = "CENTER"
        story.append(report_image)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def cleanup_previous_output():
    """Deletes the previously generated output file if it exists."""
    if st.session_state.output_file_path and os.path.exists(
        st.session_state.output_file_path
    ):
        try:
            os.remove(st.session_state.output_file_path)
            logger.info(
                f"Cleaned up previous output file: {st.session_state.output_file_path}"
            )
        except OSError as rm_err:
            logger.error(
                f"Error removing previous output file {st.session_state.output_file_path}: {rm_err}"
            )
    st.session_state.output_file_path = None
    st.session_state.output_file_name = None
    st.session_state.processing_complete = False
    st.session_state.processed_file_id = None


def handle_image_input(models, thresholds, controls, placeholder):
    # Reset video processing state if switching to image mode
    if st.session_state.processed_file_id is not None:
        cleanup_previous_output()

    uploaded_file = controls.file_uploader(
        "Upload Image", type=["jpg", "jpeg", "png", "bmp", "webp"], key="img_upload"
    )
    if uploaded_file:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            st.error("Could not decode image. Please upload a valid image file.")
            placeholder.empty()
        else:
            with st.spinner("Processing image..."):
                processed_img, detection_summary, found_defects = analyze_frame(
                    img, models, thresholds
                )

            insight_lines = build_detection_insights(detection_summary)
            report_pdf = build_pdf_report(
                uploaded_file.name,
                processed_img,
                detection_summary,
                insight_lines,
            )
            placeholder.image(processed_img, channels="BGR", use_container_width=True)
            if found_defects:
                st.success(
                    f"Detected {len(detection_summary)} road issue(s) across the selected model(s)."
                )
                st.markdown("**What this output means**")
                for line in insight_lines:
                    st.write(f"- {line}")
                st.dataframe(
                    [
                        {
                            "Model": item["model"],
                            "Defect": item["label"],
                            "Confidence": f"{item['confidence']:.2f}",
                        }
                        for item in detection_summary
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning(
                    "No confident road defects were found in this image. Try keeping both models enabled and lowering the confidence sliders for difficult images."
                )
                st.markdown("**What this output means**")
                for line in insight_lines:
                    st.write(f"- {line}")
            st.download_button(
                label="Download PDF Report",
                data=report_pdf,
                file_name=f"{Path(uploaded_file.name).stem}_road_report.pdf",
                mime="application/pdf",
                key=f"pdf_report_{uploaded_file.file_id}",
            )
    else:
        placeholder.info("Upload an image to start inspection.")


def handle_video_input(models, thresholds, controls, status_placeholder):
    uploaded_file = controls.file_uploader(
        "Upload Video", type=["mp4", "avi", "mov", "mkv"], key="vid_upload"
    )

    if uploaded_file:
        current_file_id = uploaded_file.file_id

        # Check if it's a new file upload
        if current_file_id != st.session_state.processed_file_id:
            logger.info(
                f"New video file uploaded (ID: {current_file_id}). Resetting state."
            )
            cleanup_previous_output()  # Clean up old output file before processing new one
            st.session_state.processed_file_id = current_file_id  # Set the new file ID

        # If processing is already complete for this file, just show download button
        if st.session_state.processing_complete and st.session_state.output_file_path:
            status_placeholder.success("✅ Video processing complete!")
            if os.path.exists(st.session_state.output_file_path):
                try:
                    with open(st.session_state.output_file_path, "rb") as f:
                        video_bytes = f.read()
                    st.download_button(
                        label="⬇️ Download Processed Video",
                        data=video_bytes,
                        file_name=st.session_state.output_file_name
                        or f"processed_{uploaded_file.name}",
                        mime="video/mp4",
                        key="download_btn_rerun",  # Added key for consistency
                    )
                    logger.info(
                        f"Download button shown again for already processed file: {st.session_state.output_file_path}"
                    )
                except Exception as e:
                    st.error(
                        f"Error reading previously processed video for download: {e}"
                    )
                    logger.error(
                        f"Error reading existing output file {st.session_state.output_file_path} for download",
                        exc_info=e,
                    )
                    # Maybe reset state if file reading fails?
                    # cleanup_previous_output()
            else:
                st.error("Previously processed file not found. Please upload again.")
                logger.warning(
                    f"Session state indicated processed file {st.session_state.output_file_path} but it was not found."
                )
                cleanup_previous_output()  # Reset state as the file is missing
            return  # Stop further execution in this function call

        # --- Start Processing for a new file or if not yet complete ---
        input_tmp_path = None
        output_video_path_current_run = None  # Use a temporary variable for this run
        cap = None
        writer = None
        processing_succeeded = False  # Flag to track success within try block

        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp4"
            ) as input_tmp_file:
                input_tmp_path = input_tmp_file.name
                input_tmp_file.write(uploaded_file.read())
            logger.info(f"Input video saved to temporary file: {input_tmp_path}")

            cap = cv2.VideoCapture(input_tmp_path)
            if not cap.isOpened():
                st.error("Error opening uploaded video file.")
                status_placeholder.empty()
                return

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if fps <= 0:
                fps = 30
                logger.warning("Could not read video FPS, defaulting to 30.")

            # Create a *new* temporary file for the output of this run
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp4"
            ) as output_tmp_file:
                output_video_path_current_run = output_tmp_file.name
            logger.info(
                f"Output video for this run will be saved to: {output_video_path_current_run}"
            )

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                output_video_path_current_run, fourcc, fps, (width, height)
            )
            if not writer.isOpened():
                st.error(f"Error initializing video writer.")
                logger.error(
                    f"Failed to open VideoWriter for path: {output_video_path_current_run}"
                )
                if output_video_path_current_run and os.path.exists(
                    output_video_path_current_run
                ):
                    os.remove(
                        output_video_path_current_run
                    )  # Clean up failed output file
                output_video_path_current_run = None
                return

            prog_bar = st.progress(0, text="Processing video...")
            status_placeholder.info("Processing video, please wait...")
            frame_idx = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                out_frame = process_frame(frame, models, thresholds)
                writer.write(out_frame)
                frame_idx += 1
                progress_percentage = (
                    frame_idx / total_frames if total_frames > 0 else 0
                )
                prog_text = f"Processing video... {frame_idx}/{total_frames if total_frames > 0 else '?'}"
                prog_bar.progress(min(progress_percentage, 1.0), text=prog_text)

            processing_succeeded = True  # Mark success only if loop completes
            prog_bar.progress(1.0, text="Processing complete.")
            logger.info("Video processing finished.")

        except Exception as e:
            st.error(f"An error occurred during video processing: {e}")
            logger.error("Error during video processing loop", exc_info=e)
            status_placeholder.error("Processing failed.")
            if "prog_bar" in locals():
                prog_bar.empty()  # Ensure progress bar removed on error

        finally:
            if cap is not None:
                cap.release()
            if writer is not None:
                writer.release()
            logger.info("Video capture and writer resources released.")
            if input_tmp_path and os.path.exists(input_tmp_path):
                try:
                    os.remove(input_tmp_path)
                    logger.info(f"Removed input temp file: {input_tmp_path}")
                except OSError as rm_err:
                    logger.error(
                        f"Error removing input temp file {input_tmp_path}: {rm_err}"
                    )

        # --- Post-processing logic ---
        if (
            processing_succeeded
            and output_video_path_current_run
            and os.path.exists(output_video_path_current_run)
        ):
            # Store path and status in session state
            st.session_state.output_file_path = output_video_path_current_run
            st.session_state.output_file_name = f"processed_{uploaded_file.name}"
            st.session_state.processing_complete = True
            st.session_state.processed_file_id = (
                current_file_id  # Ensure ID is set on success
            )

            status_placeholder.success("✅ Video processing complete!")
            # Now display the download button for the first time
            try:
                with open(st.session_state.output_file_path, "rb") as f:
                    video_bytes = f.read()
                st.download_button(
                    label="⬇️ Download Processed Video",
                    data=video_bytes,
                    file_name=st.session_state.output_file_name,
                    mime="video/mp4",
                    key="download_btn_first",  # Different key maybe? Helps debugging
                )
                logger.info(
                    f"Download button provided for newly processed file: {st.session_state.output_file_path}"
                )
            except Exception as e:
                st.error(f"Error reading processed video for download: {e}")
                logger.error(
                    f"Error reading output file {st.session_state.output_file_path} for download",
                    exc_info=e,
                )
                cleanup_previous_output()  # Reset state if download prep fails

        elif output_video_path_current_run and os.path.exists(
            output_video_path_current_run
        ):
            # Processing failed, clean up the output file created during this failed run
            logger.warning(
                f"Processing failed, cleaning up temporary output file: {output_video_path_current_run}"
            )
            try:
                os.remove(output_video_path_current_run)
            except OSError as rm_err:
                logger.error(
                    f"Error removing failed output temp file {output_video_path_current_run}: {rm_err}"
                )
            # Ensure session state is cleared if processing failed after a new file upload began
            if current_file_id == st.session_state.processed_file_id:
                cleanup_previous_output()

        if "prog_bar" in locals():
            prog_bar.empty()  # Final removal of progress bar

    else:
        # No file uploaded, ensure any previous state is cleared
        if st.session_state.processed_file_id is not None:
            cleanup_previous_output()
        status_placeholder.info("Upload a video to start processing.")


class YOLOVideoProcessor(VideoProcessorBase):
    def __init__(self, models, thresholds, target_width):
        self.models = models
        self.thresholds = thresholds
        self.target_width = target_width
        logger.info(
            f"YOLOVideoProcessor initialized. Target processing width: {self.target_width}"
        )

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        original_height, original_width = img.shape[:2]
        img_resized = img
        if self.target_width is not None and original_width > self.target_width:
            aspect_ratio = original_height / original_width
            target_height = int(self.target_width * aspect_ratio)
            img_resized = cv2.resize(
                img, (self.target_width, target_height), interpolation=cv2.INTER_AREA
            )
        annotated_frame_resized = process_frame(
            img_resized, self.models, self.thresholds
        )
        if img_resized is not img:
            final_frame = cv2.resize(
                annotated_frame_resized,
                (original_width, original_height),
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            final_frame = annotated_frame_resized
        return av.VideoFrame.from_ndarray(final_frame, format="bgr24")


def handle_live_camera(models, thresholds, controls, content):
    # Reset video processing state if switching to live mode
    if st.session_state.processed_file_id is not None:
        cleanup_previous_output()

    controls.info(
        "Click 'START' below to access your camera. "
        "Ensure camera permissions are granted in your browser."
    )
    media_constraints = {
        "video": {
            "width": {"ideal": 640},
            "height": {"ideal": 480},
            "frameRate": {"ideal": 15, "max": 30},
        },
        "audio": False,
    }

    def processor_factory():
        return YOLOVideoProcessor(
            models=models, thresholds=thresholds, target_width=LIVE_FEED_TARGET_WIDTH
        )

    with content:
        webrtc_ctx = webrtc_streamer(
            key="live-camera-streamer",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=processor_factory,
            media_stream_constraints=media_constraints,
            async_processing=True,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        )
        if not webrtc_ctx.state.playing:
            st.info("Camera feed stopped or not started.")


def main():
    st.set_page_config(
        layout="wide",
        page_title="Road Anomaly Detection",
        initial_sidebar_state="collapsed",
    )
    inject_premium_styles()
    render_hero()
    render_metric_cards()

    controls_col, results_col = st.columns([0.95, 1.55], gap="large")

    with controls_col:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        panel_intro(
            st,
            "Configuration",
            "Choose models, set thresholds, and define the inspection source from a focused monochrome control panel.",
        )
        use_m1 = st.checkbox("Model 1 - RoadModel YOLOv8m", value=True, key="cb_m1")
        use_m2 = st.checkbox(
            "Model 2 - YOLOv8 Small Secondary", value=True, key="cb_m2"
        )

    with controls_col:
        models_to_load = {}
        if use_m1:
            models_to_load["M1 (Model 1)"] = MODEL_PATHS["M1 (Model 1)"]
        if use_m2:
            models_to_load["M2 (Model 2)"] = MODEL_PATHS["M2 (Model 2)"]

        loaded_models = {}
        thresholds = {}
        model_load_failed = False

        if not models_to_load:
            st.warning("Select at least one model to continue.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        for name, path in models_to_load.items():
            model, names_map = load_yolo_model(path)
            if model and names_map:
                color = (
                    sv.Color.WHITE
                    if name == "M1 (Model 1)"
                    else sv.Color.from_hex("#9c9c9c")
                )
                box_ann, label_ann = make_annotators(color)
                loaded_models[name] = (model, names_map, box_ann, label_ann)
                thresholds[name] = st.slider(
                    f"{name} Confidence",
                    0.1,
                    1.0,
                    DEFAULT_CONF[name],
                    0.05,
                    key=f"{name}_conf",
                )
            else:
                model_load_failed = True

        if model_load_failed:
            st.error("One or more models failed to load. Check logs and file paths.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        input_mode = st.radio(
            "Inspection Source",
            ["Image", "Video", "Live Camera"],
            key="input_mode_radio",
        )
        st.caption("Repository: https://github.com/collabdoor/Road-Anomaly-Detection")
        st.markdown("</div>", unsafe_allow_html=True)

    with results_col:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        panel_intro(
            st,
            "Inspection Workspace",
            "Processed outputs appear here with the same restrained monochrome treatment across every mode.",
        )

        if input_mode == "Image":
            image_placeholder = st.empty()
            handle_image_input(loaded_models, thresholds, controls_col, image_placeholder)
        elif input_mode == "Video":
            video_status_placeholder = st.empty()
            handle_video_input(
                loaded_models, thresholds, controls_col, video_status_placeholder
            )
        elif input_mode == "Live Camera":
            handle_live_camera(loaded_models, thresholds, controls_col, st.container())

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="footer-card">
            Premium monochrome interface for lightweight road anomaly review. Built for static clarity and faster inspection.
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
