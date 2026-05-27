#!/usr/bin/env python3
import json
import re
from pathlib import Path


INPUT = Path("Climate_Local_News_-_Initial_may14_revised.qsf")
OUTPUT = Path("Climate_Local_News_-_Initial_may14_revised_congress_lookup.qsf")
ZIP_DISTRICT_SOURCE_URL = "https://github.com/OpenSourceActivismTech/us-zipcodes-congress"
DEFAULT_LOOKUP_URL = ""


def load_qsf(path):
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def q_by_tag(data):
    return {
        e["Payload"].get("DataExportTag"): e
        for e in data["SurveyElements"]
        if e.get("Element") == "SQ"
    }


def next_qid(data):
    max_id = 0
    for e in data["SurveyElements"]:
        if e.get("Element") == "SQ":
            m = re.fullmatch(r"QID(\d+)", e["Payload"].get("QuestionID", ""))
            if m:
                max_id = max(max_id, int(m.group(1)))
    return f"QID{max_id + 1}"


def blocks_payload(data):
    return next(e["Payload"] for e in data["SurveyElements"] if e.get("Element") == "BL")


def ensure_embedded_fields(data, fields):
    flow = next(e["Payload"] for e in data["SurveyElements"] if e.get("Element") == "FL")
    embedded = None
    for item in flow["Flow"]:
        if item.get("Type") == "EmbeddedData":
            embedded = item["EmbeddedData"]
            break
    if embedded is None:
        embedded = []
        flow["Flow"].insert(0, {"Type": "EmbeddedData", "FlowID": "FL_2", "EmbeddedData": embedded})

    existing = {x["Field"]: x for x in embedded}
    for field, default in fields:
        if field not in existing:
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
        elif default and not existing[field].get("Value"):
            existing[field]["Value"] = default


def add_question(data, payload):
    existing = q_by_tag(data).get(payload["DataExportTag"])
    if existing:
        existing["Payload"] = payload
        existing["PrimaryAttribute"] = payload["QuestionID"]
        existing["SecondaryAttribute"] = payload.get("QuestionDescription", payload["DataExportTag"])
        return

    data["SurveyElements"].append(
        {
            "SurveyID": data["SurveyEntry"]["SurveyID"],
            "Element": "SQ",
            "PrimaryAttribute": payload["QuestionID"],
            "SecondaryAttribute": payload.get("QuestionDescription", payload["DataExportTag"]),
            "TertiaryAttribute": None,
            "Payload": payload,
        }
    )


def no_copy_paste_js(existing):
    if not existing:
        return ""
    return existing.split("\n\nQualtrics.SurveyEngine.addOnReady(function() {", 1)[0].strip()


def main():
    data = load_qsf(INPUT)
    tags = q_by_tag(data)
    state_qid = tags["state"]["Payload"]["QuestionID"]
    zip_qid = tags["zip"]["Payload"]["QuestionID"]
    letter = tags["representative_letter"]["Payload"]
    intro = tags["letter_intro"]["Payload"]

    ensure_embedded_fields(
        data,
        [
            ("representativeLookupCsvUrl", DEFAULT_LOOKUP_URL),
            ("representativeZipDistrictSourceUrl", ZIP_DISTRICT_SOURCE_URL),
            ("representative_name", ""),
            ("representative_state", ""),
            ("representative_state_abbr", ""),
            ("representative_district", ""),
            ("representative_options", ""),
            ("representative_ambiguous", ""),
            ("representative_selected", ""),
            ("representative_lookup_status", ""),
        ],
    )

    existing_choice = tags.get("representative_choice")
    choice_qid = existing_choice["Payload"]["QuestionID"] if existing_choice else next_qid(data)
    choice_payload = {
        "QuestionText": "Which of the following is your congressional representative?",
        "DefaultChoices": False,
        "DataExportTag": "representative_choice",
        "QuestionType": "MC",
        "Selector": "SAVR",
        "SubSelector": "TX",
        "Configuration": {"QuestionDescriptionOption": "UseText"},
        "QuestionDescription": "representative_choice",
        "Choices": {
            str(i): {"Display": f"Representative option {i}"}
            for i in range(1, 7)
        }
        | {"7": {"Display": "I don't know"}},
        "ChoiceOrder": ["1", "2", "3", "4", "5", "6", "7"],
        "Validation": {
            "Settings": {
                "ForceResponse": "OFF",
                "ForceResponseType": "ON",
                "Type": "None",
            }
        },
        "Language": [],
        "NextChoiceId": 8,
        "NextAnswerId": 1,
        "QuestionID": choice_qid,
        "QuestionJS": "",
    }
    add_question(data, choice_payload)

    blocks = blocks_payload(data)
    for block in blocks.values():
        if block.get("Description") != "Post-treatment measures":
            continue
        elements = []
        inserted = False
        for element in block["BlockElements"]:
            if element.get("Type") == "Question" and element.get("QuestionID") == choice_qid:
                continue
            if element.get("Type") == "Question" and element.get("QuestionID") == letter["QuestionID"] and not inserted:
                elements.append({"Type": "Question", "QuestionID": choice_qid})
                inserted = True
            elements.append(element)
        block["BlockElements"] = elements
        break

    intro["QuestionText"] = intro["QuestionText"].replace(
        "your local government representative based on your zip code",
        "your congressional representative based on your ZIP code",
    )

    letter["QuestionText"] = (
        '<div id="representative-match-display" style="font-weight:600; margin-bottom:10px;">'
        "Representative: matching from ZIP code..."
        "</div>"
        "<p>You may edit the letter below before submitting it.</p>"
    )

    lookup_js = f"""
Qualtrics.SurveyEngine.addOnReady(function() {{
  var question = this;
  var container = question.getQuestionContainer();
  if (container && container.jquery) container = container[0];
  var box = container ? container.querySelector('textarea, input[type=\"text\"]') : null;
  var choiceContainer = document.getElementById('{choice_qid}');
  var display = document.getElementById('representative-match-display');
  var zip = '${{q://{zip_qid}/ChoiceTextEntryValue}}' || Qualtrics.SurveyEngine.getEmbeddedData('zip') || '';
  var selectedState = '${{q://{state_qid}/ChoiceGroup/SelectedChoices}}' || '';
  var lookupUrl = Qualtrics.SurveyEngine.getEmbeddedData('representativeLookupCsvUrl') || '';
  var reps = [];

  function parseCsv(text) {{
    var rows = [];
    var row = [];
    var value = '';
    var inQuotes = false;
    text = (text || '').replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n');
    for (var i = 0; i < text.length; i++) {{
      var ch = text.charAt(i);
      if (inQuotes) {{
        if (ch === '\"' && text.charAt(i + 1) === '\"') {{
          value += '\"';
          i++;
        }} else if (ch === '\"') {{
          inQuotes = false;
        }} else {{
          value += ch;
        }}
      }} else if (ch === '\"') {{
        inQuotes = true;
      }} else if (ch === ',') {{
        row.push(value);
        value = '';
      }} else if (ch === '\\n') {{
        row.push(value);
        rows.push(row);
        row = [];
        value = '';
      }} else {{
        value += ch;
      }}
    }}
    if (value || row.length) {{
      row.push(value);
      rows.push(row);
    }}
    if (!rows.length) return [];
    var headers = rows.shift().map(function(h) {{ return (h || '').trim(); }});
    return rows.filter(function(cells) {{ return cells.join('').trim() !== ''; }}).map(function(cells) {{
      var out = {{}};
      headers.forEach(function(h, idx) {{ out[h] = (cells[idx] || '').trim(); }});
      return out;
    }});
  }}

  function normZip(value) {{
    return (value || '').replace(/\\D/g, '').substring(0, 5);
  }}

  function labelFor(rep) {{
    var district = rep.congressional_district || rep.cd || '';
    var state = rep.state_abbr || rep.state || '';
    var suffix = state && district ? ' (' + state + '-' + district + ')' : '';
    return (rep.representative_name || 'Unnamed representative') + suffix;
  }}

  function setEmbedded(rep, status) {{
    rep = rep || {{}};
    Qualtrics.SurveyEngine.setEmbeddedData('representative_name', rep.representative_name || '');
    Qualtrics.SurveyEngine.setEmbeddedData('representative_state', rep.state || selectedState || '');
    Qualtrics.SurveyEngine.setEmbeddedData('representative_state_abbr', rep.state_abbr || '');
    Qualtrics.SurveyEngine.setEmbeddedData('representative_district', rep.congressional_district || rep.cd || '');
    Qualtrics.SurveyEngine.setEmbeddedData('representative_selected', rep.representative_name || '');
    Qualtrics.SurveyEngine.setEmbeddedData('representative_lookup_status', status || rep.lookup_status || '');
    if (display) {{
      display.textContent = rep.representative_name ? 'Representative: ' + labelFor(rep) : 'Representative: not selected';
    }}
  }}

  function fillLetter(state) {{
    if (!box || box.value) return;
    box.value = 'I am writing to express my concern about recent cuts to federal climate change preparedness programs. Our community depends on strong disaster preparedness support to protect against climate-related events that may affect ' + (state || selectedState || '[STATE]') + '.\\n\\nState and local governments lack the resources to handle catastrophic disasters alone. I urge you to advocate for restoring and strengthening federal support for climate disaster preparedness to protect vulnerable populations in our community.\\n\\nSincerely,\\n[Your name or initial]';
  }}

  function setChoiceLabel(choiceId, text, show) {{
    if (!choiceContainer) return;
    var input = choiceContainer.querySelector('input[value=\"' + choiceId + '\"], input[id$=\"-' + choiceId + '\"], input[id$=\"~' + choiceId + '\"]');
    var holder = input ? (input.closest('li') || input.closest('tr') || input.parentNode) : null;
    if (holder) holder.style.display = show ? '' : 'none';
    if (!holder) return;
    var label = holder.querySelector('label, .LabelWrapper, .ChoiceText, span');
    if (label) label.textContent = text;
  }}

  function selectedChoiceId(input) {{
    if (!input) return '';
    if (input.value) return input.value;
    var m = (input.id || '').match(/(?:-|~)(\\d+)$/);
    return m ? m[1] : '';
  }}

  function configureChoiceQuestion(matches) {{
    if (!choiceContainer) return;
    if (matches.length <= 1) {{
      choiceContainer.style.display = 'none';
      return;
    }}
    choiceContainer.style.display = '';
    for (var i = 0; i < 6; i++) {{
      setChoiceLabel(String(i + 1), matches[i] ? labelFor(matches[i]) : 'Representative option ' + (i + 1), !!matches[i]);
    }}
    setChoiceLabel('7', \"I don't know\", true);
    Array.prototype.forEach.call(choiceContainer.querySelectorAll('input[type=\"radio\"]'), function(input) {{
      input.addEventListener('change', function() {{
        var choiceId = selectedChoiceId(input);
        var idx = parseInt(choiceId, 10) - 1;
        if (choiceId === '7') {{
          setEmbedded({{}}, 'ambiguous_dont_know');
          return;
        }}
        if (matches[idx]) setEmbedded(matches[idx], 'ambiguous_selected');
      }});
    }});
  }}

  function selectedVisibleRepresentativeChoice() {{
    if (!choiceContainer || choiceContainer.style.display === 'none') return true;
    var checked = choiceContainer.querySelector('input[type="radio"]:checked');
    return !!checked;
  }}

  function applyMatches(matches) {{
    reps = matches;
    Qualtrics.SurveyEngine.setEmbeddedData('representative_options', matches.map(labelFor).join(' | '));
    Qualtrics.SurveyEngine.setEmbeddedData('representative_ambiguous', matches.length > 1 ? '1' : '0');
    configureChoiceQuestion(matches);
    if (matches.length === 1) {{
      setEmbedded(matches[0], 'single_match');
      fillLetter(matches[0].state || selectedState);
    }} else if (matches.length > 1) {{
      setEmbedded({{}}, 'ambiguous_needs_selection');
      fillLetter(matches[0].state || selectedState);
    }} else {{
      setEmbedded({{}}, 'zip_not_found_in_lookup');
      fillLetter(selectedState);
    }}
  }}

  if (choiceContainer) choiceContainer.style.display = 'none';
  fillLetter(selectedState);
  question.addOnPageSubmit(function() {{
    if (reps.length > 1 && !selectedVisibleRepresentativeChoice()) {{
      alert(\"Please select your congressional representative, or select I don't know.\");
      return false;
    }}
  }});
  if (!lookupUrl || !window.fetch) {{
    setEmbedded({{}}, lookupUrl ? 'fetch_unavailable' : 'no_lookup_url');
    return;
  }}
  fetch(lookupUrl).then(function(response) {{
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.text();
  }}).then(function(text) {{
    var five = normZip(zip);
    var seen = {{}};
    var matches = parseCsv(text).filter(function(row) {{
      var rowZip = normZip(row.zip || row.zcta);
      return five && rowZip === five;
    }}).filter(function(row) {{
      var key = [row.representative_name, row.state_abbr || row.state, row.congressional_district || row.cd].join('::');
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    }}).slice(0, 6);
    applyMatches(matches);
  }}).catch(function() {{
    setEmbedded({{}}, 'lookup_fetch_failed');
    fillLetter(selectedState);
  }});
}});
"""

    copy_part = no_copy_paste_js(letter.get("QuestionJS", ""))
    letter["QuestionJS"] = (copy_part + "\n\n" + lookup_js.strip()).strip()

    qc = next(e for e in data["SurveyElements"] if e.get("Element") == "QC")
    qc["SecondaryAttribute"] = str(sum(1 for e in data["SurveyElements"] if e.get("Element") == "SQ"))

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {OUTPUT}")
    print(f"Inserted/updated representative choice question: {choice_qid}")


if __name__ == "__main__":
    main()
