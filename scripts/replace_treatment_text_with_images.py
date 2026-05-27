#!/usr/bin/env python3
import json
import re
from pathlib import Path


INPUT = Path("Climate_Local_News_-_Initial_may14_revised_congress_lookup.qsf")
OUTPUT = Path("Climate_Local_News_-_Initial_may14_revised_congress_lookup_article_images.qsf")


def ensure_embedded_field(data, field, default=""):
    flow = next(e["Payload"] for e in data["SurveyElements"] if e.get("Element") == "FL")
    embedded = None
    for item in flow["Flow"]:
        if item.get("Type") == "EmbeddedData":
            embedded = item["EmbeddedData"]
            break
    if embedded is None:
        embedded = []
        flow["Flow"].insert(0, {"Type": "EmbeddedData", "FlowID": "FL_article_images", "EmbeddedData": embedded})
    for item in embedded:
        if item.get("Field") == field:
            if default and not item.get("Value"):
                item["Value"] = default
            return
    embedded.append(
        {
            "Description": field,
            "Type": "Recipient",
            "Field": field,
            "VariableType": "String",
            "DataVisibility": [],
            "FlowOnly": False,
            "AnalyzeText": False,
            "Value": default,
        }
    )


def main():
    data = json.loads(INPUT.read_text())
    ensure_embedded_field(data, "articleImageBaseUrl", "")
    replaced = []
    for element in data["SurveyElements"]:
        if element.get("Element") != "SQ":
            continue
        payload = element["Payload"]
        tag = payload.get("DataExportTag", "")
        if not tag.startswith("treatment_article_") or tag == "treatment_article_instructions":
            continue
        condition = tag.removeprefix("treatment_article_")
        payload["QuestionText"] = (
            '<div style="text-align:center; width:100%;">'
            f'<img src="${{e://Field/articleImageBaseUrl}}{condition}.png" '
            f'alt="News article: {condition.replace("_", " ")}" '
            'style="display:block; max-width:100%; width:760px; height:auto; margin:0 auto;" />'
            "</div>"
        )
        payload["QuestionDescription"] = tag
        payload["DataExportTag"] = tag
        replaced.append(tag)

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {OUTPUT}")
    print(f"Replaced {len(replaced)} treatment article questions")


if __name__ == "__main__":
    main()
