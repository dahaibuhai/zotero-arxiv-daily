from paper import ArxivPaper
import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
from html import escape
import smtplib
import datetime
from loguru import logger

framework = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {
      font-size: 1.3em; /* 调整星星大小 */
      line-height: 1; /* 确保垂直对齐 */
      display: inline-flex;
      align-items: center; /* 保持对齐 */
    }
    .half-star {
      display: inline-block;
      width: 0.5em; /* 半颗星的宽度 */
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""

def get_empty_html():
  block_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  </table>
  """
  return block_template

def get_block_html(title: str, authors: str, rate: str, paper_id: str, abstract: str, pdf_url: str, code_url: str = None, affiliations: str = None, keyword_hits: str = "None", source: str = "", venue: str = "", link_label: str = "PDF", score_details: str = "", score_label: str = "Relevance"):
    title = escape(title or "")
    authors = escape(authors or "")
    paper_id = escape(paper_id or "")
    abstract = escape(abstract or "")
    affiliations = escape(affiliations or "Unknown Affiliation")
    keyword_hits = escape(keyword_hits or "None")
    source = escape(source or "Unknown source")
    venue = escape(venue or "Unknown venue")
    pdf_url = escape(pdf_url or "", quote=True)
    link_label = escape(link_label or "Paper link")
    code_url = escape(code_url or "", quote=True)
    score_details = score_details or ""
    score_label = escape(score_label or "Relevance")
    code = f'<a href="{code_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 8px 16px; border-radius: 4px; margin-left: 8px;">Code</a>' if code_url else ''
    block_template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}
            <br>
            <i>{affiliations}</i>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>{score_label}:</strong> {rate}
            {score_details}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Keyword hits:</strong> {keyword_hits}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>ID:</strong> {paper_id}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Source:</strong> {source}<br>
            <strong>Venue:</strong> {venue}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>TLDR:</strong> {abstract}
        </td>
    </tr>
    <tr>
        <td style="padding: 8px 0;">
            <a href="{pdf_url}" style="display: inline-block; text-decoration: none; font-size: 14px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 8px 16px; border-radius: 4px;">{link_label}</a>
            {code}
        </td>
    </tr>
</table>
"""
    return block_template.format(
        title=title,
        authors=authors,
        rate=rate,
        paper_id=paper_id,
        abstract=abstract,
        pdf_url=pdf_url,
        code=code,
        affiliations=affiliations,
        keyword_hits=keyword_hits,
        source=source,
        venue=venue,
        link_label=link_label,
        score_details=score_details,
        score_label=score_label,
    )
  
def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def get_section_header(title: str, description: str = "") -> str:
    title = escape(title or "")
    description = escape(description or "")
    description_html = (
        f'<div style="font-size: 14px; color: #666; margin-top: 6px;">{description}</div>'
        if description
        else ""
    )
    return (
        '<div style="font-family: Arial, sans-serif; margin: 22px 0 10px 0; '
        'padding-bottom: 8px; border-bottom: 2px solid #466b8a;">'
        f'<div style="font-size: 22px; font-weight: bold; color: #24445f;">{title}</div>'
        f'{description_html}</div>'
    )


def render_paper_block(p):
    rate = get_stars(p.score)
    authors = [a.name for a in p.authors[:5]]
    authors = ', '.join(authors)
    if len(p.authors) > 5:
        authors += ', ...'

    if p.affiliations is not None:
        affiliations = p.affiliations[:5]
        affiliations = ', '.join(affiliations)
        if len(p.affiliations) > 5:
            affiliations += ', ...'
    else:
        affiliations = 'Unknown Affiliation'

    keyword_hits = ", ".join(getattr(p, "keyword_hits", [])[:8])
    if not keyword_hits:
        keyword_hits = "None"

    score_details = ""
    if getattr(p, "is_classic_fallback", False):
        publication_date = escape(getattr(p, "publication_date", "") or "Unknown")
        rate += f' <span style="color: #333;">{getattr(p, "classic_score", 0.0):.0f}/100</span>'
        score_details = (
            '<br><strong>Research relevance:</strong> '
            f'{getattr(p, "relevance_percent", 0.0):.0f}/100'
            '<br><strong>Citation impact:</strong> '
            f'{getattr(p, "impact_percent", 0.0):.0f}/100'
            '<br><strong>Citations:</strong> '
            f'{int(getattr(p, "citation_count", 0) or 0)}'
            '<br><strong>Influential citations:</strong> '
            f'{int(getattr(p, "influential_citation_count", 0) or 0)}'
            '<br><strong>Published:</strong> '
            f'{publication_date}'
        )

    source = getattr(p, "source", "")
    if getattr(p, "is_classic_fallback", False):
        source = f"{source} · Classic fallback"

    return get_block_html(
        p.title,
        authors,
        rate,
        p.arxiv_id,
        p.tldr,
        p.pdf_url,
        p.code_url,
        affiliations,
        keyword_hits,
        source,
        getattr(p, "venue", ""),
        getattr(p, "link_label", "PDF"),
        score_details,
        "Overall recommendation" if getattr(p, "is_classic_fallback", False) else "Relevance",
    )


def render_email(papers: list[ArxivPaper]):
    if len(papers) == 0:
        return framework.replace('__CONTENT__', get_empty_html())

    arxiv_papers = [
        paper for paper in papers if getattr(paper, "source", "") == "arXiv"
    ]
    new_semantic_papers = [
        paper for paper in papers
        if getattr(paper, "source", "") == "Semantic Scholar"
        and not getattr(paper, "is_classic_fallback", False)
    ]
    other_papers = [
        paper for paper in papers
        if getattr(paper, "source", "") not in ("arXiv", "Semantic Scholar")
        and not getattr(paper, "is_classic_fallback", False)
    ]
    classic_papers = [
        paper for paper in papers if getattr(paper, "is_classic_fallback", False)
    ]
    sections = []
    with tqdm(total=len(papers), desc='Rendering Email') as progress:
        for title, section_papers in (
            ("New arXiv papers", arxiv_papers),
            ("New Semantic Scholar papers", new_semantic_papers),
            ("Other new papers", other_papers),
        ):
            if section_papers:
                parts = []
                for paper in section_papers:
                    parts.append(render_paper_block(paper))
                    progress.update(1)
                sections.append(
                    get_section_header(f"{title} ({len(section_papers)})")
                    + '<br>'.join(parts)
                )

        if classic_papers:
            classic_parts = []
            for paper in classic_papers:
                classic_parts.append(render_paper_block(paper))
                progress.update(1)
            sections.append(
                get_section_header(
                    f"Classic high-impact papers ({len(classic_papers)})",
                    "New Semantic Scholar papers did not fill today's quota. "
                    "These older papers passed the relevance and citation-impact gates.",
                )
                + '<br>'.join(classic_parts)
            )

    content = '<br>' + '<br>'.join(sections) + '</br>'
    return framework.replace('__CONTENT__', content)

def send_email(sender:str, receiver:str, password:str,smtp_server:str,smtp_port:int, html:str,):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = _format_addr('Github Action <%s>' % sender)
    msg['To'] = _format_addr('You <%s>' % receiver)
    today = datetime.datetime.now().strftime('%Y/%m/%d')
    msg['Subject'] = Header(f'Daily literature {today}', 'utf-8').encode()

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
    except Exception as e:
        logger.warning(f"Failed to use TLS. {e}")
        logger.warning(f"Try to use SSL.")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)

    server.login(sender, password)
    server.sendmail(sender, [receiver], msg.as_string())
    server.quit()
