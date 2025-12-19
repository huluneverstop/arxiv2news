import fitz  # PyMuPDF
import argparse
import os
import base64
import io
from PIL import Image, ImageDraw, ImageFont
import dashscope
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"
load_dotenv()


# QwenClient：官方 MultiModalConversation 模式
class QwenClient:
    def __init__(self, api_key: str):
        self.api_key = '...'#输入apikey
        self.model = "qwen3-vl-30b-a3b-instruct"#"qwen3-vl-8b-instruct"

    def ask_with_image(self, prompt: str, image_pil) -> str:
        """使用官方示例的 MultiModalConversation.call"""

        # --- 将 PIL 图像转 base64 ---
        buffer = io.BytesIO()
        image_pil.save(buffer, format="PNG")
        image_b64 = base64.b64encode(buffer.getvalue()).decode()

        # ★ 关键：包装成 data URL，避免被当成普通 URL 校验
        image_data_url = f"data:image/png;base64,{image_b64}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"image": image_data_url},
                    {"text": prompt}
                ],
            }
        ]

        # --- 调用 API ---
        response = dashscope.MultiModalConversation.call(
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            max_tokens=1000,
            temperature=0.3,
        )

        if not hasattr(response, "output") or response.output is None:
            
            raise RuntimeError(
                f"DashScope 调用失败: status={getattr(response, 'status_code', None)}, "
                f"code={getattr(response, 'code', None)}, "
                f"message={getattr(response, 'message', None)}"
            )

        try:
            text = response.output.choices[0].message.content[0]["text"]
            return text
        except Exception as e:
            raise RuntimeError(f"Qwen3-VL 返回解析失败: {e}\n原始返回: {response}")


# Caption 渲染
def text_size(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def wrap_paragraph(text, font, max_width, draw):

    words = text.split(" ")
    lines, line = [], ""

    for w in words:
        test = (line + " " + w) if line else w
        width, _ = text_size(draw, test, font)
        if width <= max_width:
            line = test
        else:
            lines.append(line)
            line = w

    if line:
        lines.append(line)
    return lines


def add_caption(img, caption, font_path="/media/home/pengyunning/arXiv2xhs/times.ttf", font_size=26, margin=25):
    img_w, img_h = img.size
    font = ImageFont.truetype(font_path, font_size)

    tmp = Image.new("RGB", (img_w, img_h))
    dtmp = ImageDraw.Draw(tmp)

    lines = wrap_paragraph(caption, font, img_w - 2 * margin, dtmp)
    _, line_height = text_size(dtmp, "A", font)
    cap_h = len(lines) * line_height + (len(lines) - 1) * 8 + 2 * margin

    canvas = Image.new("RGB", (img_w, img_h + cap_h), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)

    y = img_h + margin
    for line in lines:
        draw.text((margin, y), line, font=font, fill="black")
        y += line_height + 8

    return canvas


# ======================================================
# 调用 Qwen3-VL 获取 bounding boxes
# ======================================================
def get_bboxes(client, page_img):
    # prompt = """
    # You are an expert in scientific document layout analysis. 
    # Your task is to detect ONLY the complete "Figure Blocks" on this PDF page. 
    
    # A Figure Block is defined as a rectangular region that: 
    # 1. Contains one or more images (figures, diagrams, plots, visualizations), AND 
    # 2. Contains a caption directly associated with the figure, where the caption MUST begin with patterns such as: 
    # - "Figure 1", "Figure 2", ... - "Fig. 1", "Fig. 2", ... - "Figure:", "Fig:" 
    # - or any similar academic figure labeling convention. 
    # 3. Includes the whitespace that visually groups the image(s) and its caption together. 
    
    # Important rules: 
    # - You MUST locate only figure blocks that have a caption visibly attached to the image. 
    # - Do NOT detect images without captions. - Do NOT detect captions without images. 
    # - Do NOT detect unrelated text, tables, equations, headers, footers, titles, or page decorations. 
    
    # Output: 
    # Return a pure Python list of bounding boxes for each complete figure block: 
    # [[x1, y1, x2, y2], [x1, y1, x2, y2], ...] 
    
    # Bounding box requirements: 
    # - Each bounding box must tightly enclose BOTH: 
    # • the entire figure content, AND 
    # • the entire caption text beneath it. 
    # - Include small surrounding whitespace so the figure block forms a coherent rectangle. 
    
    # Restrictions: 
    # - Output ONLY the Python list. 
    # - No explanations, no comments, no additional text.
    # """
    prompt="""You are a scientific document layout analyzer.

    Your task: detect ONLY the complete Figure Blocks on this page.
    A Figure Block MUST contain:
    1. One or more images (figures) AND
    2. A caption starting with: "Figure", "FIG.", "Fig."

    You MUST output a valid Python list.

    STRICT RULES:
    - bbox MUST be normalized floats (0–1).
    - Output ONLY JSON. No explanations. No markdown.
    - If you are unsure, make the bbox smaller, not larger.
    - If you have provided an incorrect format, I shall attempt again.

    Example output:
    [[0.12, 0.18, 0.83, 0.52],...]
    """

    # output = client.ask_with_image(prompt, page_img)
    try:
        output = client.ask_with_image(prompt, page_img)
    except Exception as e:
        print("❌ Qwen3-VL 调用失败:", e)
        return []
    print("模型返回:", output)

    try:
        bboxes = eval(output)
        if isinstance(bboxes, list):
            return bboxes
        else:
            return []
    except:
        print("⚠ 无法将输出解析为 Python 列表")
        return []


# ======================================================
# PDF → 截图 → 调 Qwen → 裁剪 → Caption → 保存
# ======================================================
def process_pdf(pdf_path, output_dir, api_key):
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(output_dir, timestamp)
    os.makedirs(output_dir, exist_ok=True)

    client = QwenClient(api_key)
    doc = fitz.open(pdf_path)
    print(f"PDF 共有 {len(doc)} 页")

    fig_id = 1

    for i, page in enumerate(doc):
        print(f"\n=== 处理中: 页 {i+1} ===")

        mat = fitz.Matrix(3, 3)  # 300DPI
        pix = page.get_pixmap(matrix=mat)
        page_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        W, H =page_img.width, page_img.height

        # bboxes = get_bboxes(client, page_img)
        bboxes = [[106, 87, 903, 524], [536, 541, 886, 699]]
        print("识别到bbox:", bboxes)

        for box in bboxes:
            # 无归一化原始像素框坐标
            # x1, y1, x2, y2 = box
            # x1 = int(x1 / 1024 * W)
            # y1 = int(y1 / 1024 * H)
            # x2 = int(x2 / 1024 * W)
            # y2 = int(y2 / 1024 * H)

            #归一化坐标
            x1n, y1n, x2n, y2n = box
            x1 = int(x1n * W)
            y1 = int(y1n * H)
            x2 = int(x2n * W)
            y2 = int(y2n * H)

            crop = page_img.crop((x1, y1, x2, y2))
            final_img = crop

            # caption = f"Figure {fig_id}. Extracted automatically by Qwen3-VL."
            # final_img = add_caption(crop, caption)

            save_path = os.path.join(output_dir, f"Page_{i+1}_figure_{fig_id}.png")
            final_img.save(save_path, dpi=(300, 300))

            print(f"已保存: {save_path}")
            fig_id += 1

    print("\n 图像已提取完成！")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default='/media/home/pengyunning/arXiv2xhs/2511.19827v1.pdf', help="Input PDF")
    parser.add_argument("--output", default='/media/home/pengyunning/arXiv2xhs/output/20251205/', help="Output directory")
    args = parser.parse_args()

    process_pdf(args.pdf, args.output, os.getenv('API_KEY'))