/**
 * profile-fields.js
 * Shared field-visibility and data logic for Profile (edit mode)
 * and Registration forms.  Both pages import this file and call
 * the exported helpers with their own DOM references.
 *
 * Exposed as a plain global  window.ProfileFields  so it works
 * without a module bundler.
 */

(function (global) {
    "use strict";

    // ── Country → curriculum ─────────────────────────────────────────────────
    var DERIVED_CURRICULUM = {
        "Nepal":          "NEB/CTEVT",
        "United States":  "US Common Core/AP",
        "United Kingdom": "A-Levels/GCSE",
        "Australia":      "HSC/VCE/SACE",
        "Canada":         "Provincial/IB",
        "India":          "CBSE/ICSE/State Boards"
    };

    // ── Level options per country ────────────────────────────────────────────
    var LEVEL_OPTIONS = {
        "Nepal": [
            "Class 6","Class 7","Class 8","Class 9","Class 10",
            "Class 11","Class 12","Bachelors","Masters"
        ],
        "__default__": [
            "Class 6","Class 7","Class 8","Class 9","Class 10",
            "Class 11","Class 12","Bachelors","Masters"
        ]
    };

    // ── Timezone data ────────────────────────────────────────────────────────
    var DEFAULT_TIMEZONES = {
        "Nepal":          "Asia/Kathmandu",
        "United Kingdom": "Europe/London",
        "South Korea":    "Asia/Seoul",
        "China":          "Asia/Shanghai",
        "Germany":        "Europe/Berlin",
        "Japan":          "Asia/Tokyo",
        "India":          "Asia/Kolkata"
    };
    var MULTI_TIMEZONE_OPTIONS = {
        "United States": ["America/New_York","America/Chicago","America/Denver",
                          "America/Los_Angeles","America/Anchorage","Pacific/Honolulu"],
        "Canada":        ["America/Toronto","America/Winnipeg","America/Edmonton",
                          "America/Vancouver","America/Halifax","America/St_Johns"],
        "Australia":     ["Australia/Sydney","Australia/Melbourne","Australia/Brisbane",
                          "Australia/Adelaide","Australia/Perth"]
    };

    // ── Faculty / Program data ───────────────────────────────────────────────
    var NEB_GENERAL_FACULTIES = [
        "Science Faculty",
        "Management Faculty (Commerce)",
        "Humanities and Social Sciences Faculty (Arts)",
        "Law Faculty",
        "Education Faculty"
    ];
    var NEB_TECHNICAL_STREAMS = [
        "Computer Engineering",
        "Civil Engineering",
        "Electrical/Electronics Engineering",
        "Agriculture and Animal Science",
        "Forestry",
        "Nursing (PCL Nursing)",
        "Pharmacy",
        "Medical Lab Technology (CMLT)",
        "Hotel Management & Culinary Arts"
    ];

    // BSc IT = explicit duration (3 or 4 years).
    // BSc CSIT = implicit 4-year TU standard — no duration field shown.
    var NEPAL_BACHELORS_PROGRAMS = [
        "BBA","BCA","BE Computer","BE Civil","BIT",
        "BSc IT",
        "BSc CSIT",
        "BSc Nursing","BTech","MBBS"
    ];
    var NEPAL_MASTERS_PROGRAMS = [
        "MBA","MCA","MIT","MSc Computer Science"
    ];

    // ── Program Duration data ────────────────────────────────────────────────
    // ONLY programs in this list trigger the Duration selector.
    // BSc CSIT excluded intentionally.
    var PROGRAMS_WITH_DURATION_ARR = ["BSc IT"];

    var DURATION_OPTIONS = {
        "BSc IT": [
            { value: "3 Years", label: "3 Years (International-affiliated, e.g. APU/LBEF)" },
            { value: "4 Years", label: "4 Years (TU-affiliated BSc CSIT)" }
        ]
    };

    // Number of semesters generated per duration
    var SEMESTER_COUNTS = {
        "3 Years": 6,
        "4 Years": 8
    };

    var DEFAULT_SEMESTER_COUNT = 8;

    // ── Grade label map ──────────────────────────────────────────────────────
    var GRADE_LABELS = {
        "Class 6":  { label: "Class 5 Final Grade %",        hint: "Enter your Class 5 final grade percentage." },
        "Class 7":  { label: "Class 6 Final Grade %",        hint: "Enter your Class 6 final grade percentage." },
        "Class 8":  { label: "Class 7 Final Grade %",        hint: "Enter your Class 7 final grade percentage." },
        "Class 9":  { label: "Class 8 Final Grade %",        hint: "Enter your Class 8 final grade percentage." },
        "Class 10": { label: "Class 9 Final Grade %",        hint: "Enter your Class 9 final grade percentage." },
        "Class 11": { label: "SEE / Class 10 Final Grade %", hint: "Enter your SEE or Class 10 percentage." },
        "Class 12": { label: "Class 11 Final Grade %",       hint: "Enter your Class 11 final percentage." },
        "Bachelors":{ label: "Class 12 / +2 Final Grade %",  hint: "Enter your Class 12 / +2 board exam percentage." },
        "Masters":  { label: "Bachelors CGPA / Grade %",     hint: "Enter your Bachelors cumulative GPA or percentage." }
    };

    // ── Internal ─────────────────────────────────────────────────────────────
    function hasDuration(program) {
        return PROGRAMS_WITH_DURATION_ARR.indexOf(program) !== -1;
    }

    // ── Public helpers ───────────────────────────────────────────────────────

    /** Build ["Semester 1", ..., "Semester N"] */
    function buildSemesterOptions(count) {
        var opts = [];
        for (var i = 1; i <= count; i++) { opts.push("Semester " + i); }
        return opts;
    }

    /** (Re)populate a <select> with an items array. */
    function populateSelect(selectEl, items, placeholder, selected) {
        selectEl.innerHTML = '<option value="">' + placeholder + '</option>';
        items.forEach(function (item) {
            var opt = document.createElement("option");
            opt.value = item;
            opt.textContent = item;
            if (item === selected) opt.selected = true;
            selectEl.appendChild(opt);
        });
    }

    /**
     * Show/hide the Program Duration field and refresh semester options.
     * Call when the Faculty/Program select changes.
     */
    function updateProgramDuration(program, durationGroupEl, durationSelectEl, semesterSelectEl, savedDuration, savedSemester) {
        if (!durationGroupEl) return;
        var show = hasDuration(program);
        durationGroupEl.style.display = show ? "" : "none";

        if (show) {
            var opts = DURATION_OPTIONS[program] || [];
            durationSelectEl.innerHTML = '<option value="">-- Select Duration --</option>';
            opts.forEach(function (opt) {
                var el = document.createElement("option");
                el.value = opt.value;
                el.textContent = opt.label;
                if (opt.value === savedDuration) el.selected = true;
                durationSelectEl.appendChild(el);
            });
            var cur = durationSelectEl.value;
            if (cur && SEMESTER_COUNTS[cur] && semesterSelectEl) {
                populateSelect(semesterSelectEl, buildSemesterOptions(SEMESTER_COUNTS[cur]),
                               "-- Select Term --", savedSemester || "");
            }
        } else {
            if (durationSelectEl) durationSelectEl.innerHTML = '<option value="">-- Select Duration --</option>';
            if (semesterSelectEl) {
                var std = buildSemesterOptions(DEFAULT_SEMESTER_COUNT)
                              .concat(["Year 1","Year 2","Year 3","Year 4"]);
                populateSelect(semesterSelectEl, std, "-- Select Term --", savedSemester || "");
            }
        }
    }

    /** Refresh semester options when the Duration select itself changes. */
    function onDurationChange(durationValue, semesterSelectEl, savedSemester) {
        if (!durationValue || !SEMESTER_COUNTS[durationValue] || !semesterSelectEl) return;
        populateSelect(semesterSelectEl,
                       buildSemesterOptions(SEMESTER_COUNTS[durationValue]),
                       "-- Select Term --", savedSemester || "");
    }

    /**
     * Show/hide the University field group (Nepal Bachelors/Masters only).
     * Call when country or study level changes.
     */
    function updateUniversityGroup(country, level, uniGroupEl, uniSelectEl, uniCustomGroupEl, uniCustomInputEl, uniCustomLabelEl) {
        if (!uniGroupEl) return;
        var show = (country === "Nepal" && (level === "Bachelors" || level === "Masters"));
        uniGroupEl.style.display = show ? "" : "none";
        if (uniSelectEl) uniSelectEl.required = show;
        if (!show) {
            if (uniSelectEl)       uniSelectEl.value = "";
            if (uniCustomGroupEl)  uniCustomGroupEl.style.display = "none";
            if (uniCustomInputEl)  { uniCustomInputEl.value = ""; uniCustomInputEl.required = false; }
        } else {
            refreshUniversityCustom(
                uniSelectEl ? uniSelectEl.value : "",
                uniCustomGroupEl, uniCustomInputEl, uniCustomLabelEl
            );
        }
    }

    /**
     * Toggle the custom-text input when Foreign-Affiliated / Other selected.
     * Call on the universitySelect change event.
     */
    function refreshUniversityCustom(uniValue, uniCustomGroupEl, uniCustomInputEl, uniCustomLabelEl) {
        if (!uniCustomGroupEl) return;
        var need = (uniValue === "Foreign-Affiliated" || uniValue === "Other");
        uniCustomGroupEl.style.display = need ? "" : "none";
        if (uniCustomInputEl) uniCustomInputEl.required = need;
        if (need && uniCustomLabelEl) {
            if (uniValue === "Foreign-Affiliated") {
                uniCustomLabelEl.innerHTML = 'Specify affiliated institution <span class="text-danger">*</span>';
                if (uniCustomInputEl) uniCustomInputEl.placeholder = "e.g. London Metropolitan University";
            } else {
                uniCustomLabelEl.innerHTML = 'Specify university <span class="text-danger">*</span>';
                if (uniCustomInputEl) uniCustomInputEl.placeholder = "e.g. Gandaki University";
            }
        }
        if (!need && uniCustomInputEl) uniCustomInputEl.value = "";
    }

    function defaultTimezone(country) {
        if (MULTI_TIMEZONE_OPTIONS[country]) return MULTI_TIMEZONE_OPTIONS[country][0];
        return DEFAULT_TIMEZONES[country] || "UTC";
    }

    function levelsForCountry(country) {
        return LEVEL_OPTIONS[country] || LEVEL_OPTIONS["__default__"];
    }

    function curriculumForCountry(country) {
        return DERIVED_CURRICULUM[country] || "National";
    }

    // ── Export ───────────────────────────────────────────────────────────────
    global.ProfileFields = {
        // Data
        DERIVED_CURRICULUM:       DERIVED_CURRICULUM,
        LEVEL_OPTIONS:            LEVEL_OPTIONS,
        DEFAULT_TIMEZONES:        DEFAULT_TIMEZONES,
        MULTI_TIMEZONE_OPTIONS:   MULTI_TIMEZONE_OPTIONS,
        NEB_GENERAL_FACULTIES:    NEB_GENERAL_FACULTIES,
        NEB_TECHNICAL_STREAMS:    NEB_TECHNICAL_STREAMS,
        NEPAL_BACHELORS_PROGRAMS: NEPAL_BACHELORS_PROGRAMS,
        NEPAL_MASTERS_PROGRAMS:   NEPAL_MASTERS_PROGRAMS,
        PROGRAMS_WITH_DURATION:   PROGRAMS_WITH_DURATION_ARR,
        DURATION_OPTIONS:         DURATION_OPTIONS,
        SEMESTER_COUNTS:          SEMESTER_COUNTS,
        DEFAULT_SEMESTER_COUNT:   DEFAULT_SEMESTER_COUNT,
        GRADE_LABELS:             GRADE_LABELS,

        // Helpers
        buildSemesterOptions:     buildSemesterOptions,
        populateSelect:           populateSelect,
        updateProgramDuration:    updateProgramDuration,
        onDurationChange:         onDurationChange,
        updateUniversityGroup:    updateUniversityGroup,
        refreshUniversityCustom:  refreshUniversityCustom,
        defaultTimezone:          defaultTimezone,
        levelsForCountry:         levelsForCountry,
        curriculumForCountry:     curriculumForCountry
    };

}(window));

