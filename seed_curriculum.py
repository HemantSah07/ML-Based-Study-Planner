import json
from datetime import datetime
from app import create_app, db
from app.models import Subject, Chapter, Topic, Subtopic, LearningMaterial, Flashcard, AssessmentQuestion

app = create_app()

def seed_curriculum():
    with app.app_context():
        print("Clearing curriculum tables to ensure fresh seed...")
        # (Be careful not to delete users or profiles, just clear curriculum/questions/materials to avoid duplicates)
        db.session.query(LearningMaterial).delete()
        db.session.query(Subtopic).delete()
        db.session.query(Topic).delete()
        db.session.query(Chapter).delete()
        db.session.query(Flashcard).delete()
        db.session.query(AssessmentQuestion).delete()
        # Keep existing subjects, but clear them if they overlap with our new structured seeding
        db.session.query(Subject).delete()
        db.session.commit()

        print("Seeding subjects...")
        
        # Helper to insert subjects
        def add_subject(code, name, ch, diff, lvl, prog, sem, country="Nepal", curr="National"):
            sub = Subject(
                code=code, name=name, credit_hours=ch, difficulty_level=diff,
                level_of_study=lvl, program=prog, semester=sem, semester_tag=f"Y1S1",
                country=country, curriculum=curr
            )
            db.session.add(sub)
            db.session.flush()
            return sub

        # --- CLASS 8 ---
        sub_c8_math = add_subject("C8-MATH", "Mathematics", 4, 3, "Class 8", None, "Class 8")
        sub_c8_sci = add_subject("C8-SCI", "Science", 4, 4, "Class 8", None, "Class 8")
        add_subject("C8-ENG", "English", 4, 3, "Class 8", None, "Class 8")
        add_subject("C8-NEP", "Nepali", 4, 3, "Class 8", None, "Class 8")
        add_subject("C8-SOC", "Social Studies", 4, 2, "Class 8", None, "Class 8")
        add_subject("C8-HEA", "Health & Physical Education", 3, 2, "Class 8", None, "Class 8")
        add_subject("C8-COM", "Computer Science", 3, 2, "Class 8", None, "Class 8")
        add_subject("C8-MOR", "Moral Education", 2, 1, "Class 8", None, "Class 8")

        # --- CLASS 9 ---
        add_subject("C9-MATH", "Mathematics", 4, 4, "Class 9", "General", "Class 9")
        add_subject("C9-SCI", "Science", 4, 4, "Class 9", "General", "Class 9")
        add_subject("C9-ENG", "English", 4, 3, "Class 9", "General", "Class 9")
        add_subject("C9-NEP", "Nepali", 4, 3, "Class 9", "General", "Class 9")
        add_subject("C9-SOC", "Social Studies", 4, 3, "Class 9", "General", "Class 9")
        add_subject("C9-HPE", "Health and Population", 3, 2, "Class 9", "General", "Class 9")
        add_subject("C9-OPM", "Optional Mathematics", 4, 5, "Class 9", "General", "Class 9")
        add_subject("C9-COM", "Computer Science", 3, 3, "Class 9", "General", "Class 9")

        # --- CLASS 10 (SEE) ---
        sub_see_math = add_subject("SEE-MATH", "Mathematics", 4, 4, "Class 10 (Secondary Education Examination - SEE)", None, "Class 10")
        sub_see_sci = add_subject("SEE-SCI", "Science", 4, 4, "Class 10 (Secondary Education Examination - SEE)", None, "Class 10")
        add_subject("SEE-ENG", "English", 4, 3, "Class 10 (Secondary Education Examination - SEE)", None, "Class 10")
        add_subject("SEE-NEP", "Nepali", 4, 3, "Class 10 (Secondary Education Examination - SEE)", None, "Class 10")
        add_subject("SEE-SOC", "Social Studies", 4, 3, "Class 10 (Secondary Education Examination - SEE)", None, "Class 10")
        add_subject("SEE-OPM", "Optional Mathematics", 4, 5, "Class 10 (Secondary Education Examination - SEE)", None, "Class 10")

        # --- CLASS 11 (Science & Management Streams) ---
        sub_c11_phy = add_subject("C11-PHY", "Physics", 4, 4, "Class 11", "Science Stream", "Class 11")
        sub_c11_chem = add_subject("C11-CHM", "Chemistry", 4, 4, "Class 11", "Science Stream", "Class 11")
        add_subject("C11-ENG", "English", 4, 2, "Class 11", "Science Stream", "Class 11")
        add_subject("C11-NEP", "Nepali", 4, 2, "Class 11", "Science Stream", "Class 11")
        add_subject("C11-MAT", "Mathematics", 4, 4, "Class 11", "Science Stream", "Class 11")
        add_subject("C11-COM", "Computer Science", 4, 3, "Class 11", "Science Stream", "Class 11")

        add_subject("C11-ACC", "Accountancy", 4, 3, "Class 11", "Management", "Class 11")
        add_subject("C11-ECO", "Economics", 4, 3, "Class 11", "Management", "Class 11")
        add_subject("C11-BST", "Business Studies", 4, 2, "Class 11", "Management", "Class 11")
        add_subject("C11-ENG-M", "English", 4, 2, "Class 11", "Management", "Class 11")
        add_subject("C11-NEP-M", "Nepali", 4, 2, "Class 11", "Management", "Class 11")

        # --- CLASS 12 (Science & Management Streams) ---
        sub_c12_phy = add_subject("C12-PHY", "Physics", 4, 4, "Class 12 (National Examination Board - NEB)", "Science Stream", "Class 12")
        add_subject("C12-CHM", "Chemistry", 4, 4, "Class 12 (National Examination Board - NEB)", "Science Stream", "Class 12")
        add_subject("C12-MAT", "Mathematics", 4, 4, "Class 12 (National Examination Board - NEB)", "Science Stream", "Class 12")
        add_subject("C12-ENG", "English", 4, 2, "Class 12 (National Examination Board - NEB)", "Science Stream", "Class 12")
        add_subject("C12-NEP", "Nepali", 4, 2, "Class 12 (National Examination Board - NEB)", "Science Stream", "Class 12")

        add_subject("C12-ACC", "Accountancy", 4, 3, "Class 12 (National Examination Board - NEB)", "Management", "Class 12")
        add_subject("C12-ECO", "Economics", 4, 3, "Class 12 (National Examination Board - NEB)", "Management", "Class 12")
        add_subject("C12-BST", "Business Studies", 4, 2, "Class 12 (National Examination Board - NEB)", "Management", "Class 12")

        # --- BACHELOR'S ---
        # BSc CSIT
        sub_csit_c = add_subject("CSIT-102", "C Programming", 3, 4, "Bachelor's", "BSc CSIT", "Semester 1")
        sub_csit_dl = add_subject("CSIT-103", "Digital Logic", 3, 3, "Bachelor's", "BSc CSIT", "Semester 1")
        add_subject("CSIT-101", "Introduction to Information Technology", 3, 2, "Bachelor's", "BSc CSIT", "Semester 1")
        add_subject("CSIT-104", "Mathematics I", 3, 4, "Bachelor's", "BSc CSIT", "Semester 1")
        add_subject("CSIT-105", "Physics", 3, 4, "Bachelor's", "BSc CSIT", "Semester 1")
        add_subject("CSIT-106", "Communication Techniques", 3, 2, "Bachelor's", "BSc CSIT", "Semester 1")
        
        # BBA
        sub_bba_math = add_subject("BBA-101", "Business Mathematics", 3, 3, "Bachelor's", "BBA", "Semester 1")
        add_subject("BBA-102", "Marketing", 3, 2, "Bachelor's", "BBA", "Semester 1")
        add_subject("BBA-103", "Economics", 3, 3, "Bachelor's", "BBA", "Semester 1")
        add_subject("BBA-104", "Accounting", 3, 3, "Bachelor's", "BBA", "Semester 1")
        add_subject("BBA-105", "Business Communication", 3, 2, "Bachelor's", "BBA", "Semester 1")

        # MBBS
        add_subject("MBBS-101", "Anatomy", 4, 5, "Bachelor's", "MBBS", "Professional Year 1")
        add_subject("MBBS-102", "Physiology", 4, 4, "Bachelor's", "MBBS", "Professional Year 1")
        add_subject("MBBS-103", "Biochemistry", 3, 4, "Bachelor's", "MBBS", "Professional Year 1")

        # --- MASTER'S ---
        # MBA
        sub_mba_econ = add_subject("MBA-501", "Managerial Economics", 3, 4, "Master's", "MBA", "Semester 1")
        add_subject("MBA-502", "Financial Management", 3, 4, "Master's", "MBA", "Semester 1")
        add_subject("MBA-503", "Marketing", 3, 3, "Master's", "MBA", "Semester 1")
        add_subject("MBA-504", "Organizational Behaviour", 3, 2, "Master's", "MBA", "Semester 1")
        add_subject("MBA-505", "Business Statistics", 3, 3, "Master's", "MBA", "Semester 1")

        # MSc Computer Science
        sub_msc_ml = add_subject("MSC-502", "Machine Learning", 3, 5, "Master's", "MSc Computer Science", "Semester 1")
        add_subject("MSC-501", "Advanced Algorithms", 3, 4, "Master's", "MSc Computer Science", "Semester 1")
        add_subject("MSC-503", "Artificial Intelligence", 3, 4, "Master's", "MSc Computer Science", "Semester 1")
        add_subject("MSC-504", "Research Methodology", 3, 3, "Master's", "MSc Computer Science", "Semester 1")
        add_subject("MSC-505", "Advanced Database Systems", 3, 4, "Master's", "MSc Computer Science", "Semester 1")
        add_subject("MSC-506", "Distributed Systems", 3, 4, "Master's", "MSc Computer Science", "Semester 1")

        # Seed standard fallbacks for remaining semesters for validation
        programs = ["BSc CSIT", "BIT", "BBA", "BCA", "BTech", "BSc Nursing", "BE Civil", "BE Computer", "MSc Computer Science", "MIT", "MCA", "MBA"]
        for p in programs:
            levels = "Bachelor's" if p in ["BSc CSIT", "BIT", "BBA", "BCA", "BTech", "BSc Nursing", "BE Civil", "BE Computer"] else "Master's"
            sems = range(1, 9) if levels == "Bachelor's" else range(1, 5)
            for s in sems:
                # check if subject already seeded for Semester s
                exists = Subject.query.filter_by(program=p, semester=f"Semester {s}").first()
                if not exists:
                    add_subject(f"SUB-{p.replace(' ', '')}-{s}01", f"Core Subject I", 3, 3, levels, p, f"Semester {s}")
                    add_subject(f"SUB-{p.replace(' ', '')}-{s}02", f"Core Subject II", 3, 3, levels, p, f"Semester {s}")

        print("Subjects seeded successfully.")

        # --- SEED CHAPTERS, TOPICS, SUBTOPICS, AND LEARNING MATERIALS ---
        # Define detailed textbook curriculum content for C Programming
        c_prog_chapters = [
            {
                "chapter_number": 1,
                "name": "Fundamentals of C Programming",
                "topics": [
                    {
                        "topic_number": 1,
                        "name": "Data Types and Variables",
                        "subtopics": ["Keywords and Identifiers", "Primitive Data Types (int, float, char, double)", "Variable Declarations and Rules"],
                        "material": {
                            "title": "Data Types and Variables in C Programming",
                            "learning_objectives": "<ul><li>Understand the concept of keywords and identifiers in C.</li><li>Distinguish between different primitive data types and their memory allocations.</li><li>Write programs that declare, initialize, and print variables correctly.</li></ul>",
                            "introduction": "<p>In C Programming, variables are named storage locations in memory. Every variable must have a defined data type that informs the compiler how much memory space to allocate and how to interpret the binary values stored within it.</p>",
                            "detailed_explanation": "<p>A primitive data type is one built directly into the C compiler. The four basic primitive types are:</p><ul><li><strong>int</strong>: Used to store integers. Typically occupies 4 bytes of memory (on modern architectures), spanning values from -2,147,483,648 to 2,147,483,647.</li><li><strong>char</strong>: Used to store single characters. Occupies exactly 1 byte of memory and maps characters to integer values using the ASCII table (e.g. 'A' represents value 65).</li><li><strong>float</strong>: Used to store single-precision fractional/floating-point values. Occupies 4 bytes.</li><li><strong>double</strong>: Used to store double-precision floating-point values. Occupies 8 bytes and offers greater precision.</li></ul>",
                            "important_definitions": "<p><strong>Variable</strong>: An identifier representing a memory address where values can be written, updated, and read.</p><p><strong>Identifier</strong>: The unique name assigned to variables, functions, and arrays in code.</p>",
                            "concepts": "<p>Variable naming rules in C: Names can contain letters, digits, and underscores, but MUST start with a letter or underscore. Keywords (reserved terms like <code>return</code>, <code>if</code>, <code>while</code>) cannot be used as variable names.</p>",
                            "examples": "<pre><code>int age = 19;\nchar grade = 'A';\ndouble gpa = 3.82;</code></pre>",
                            "worked_examples": "<p><strong>Problem:</strong> Write a C program to swap the values of two integer variables without using a third variable.</p><pre><code>#include &lt;stdio.h&gt;\nint main() {\n    int a = 10, b = 20;\n    a = a + b; // a becomes 30\n    b = a - b; // b becomes 10 (30 - 20)\n    a = a - b; // a becomes 20 (30 - 10)\n    printf(\"a = %d, b = %d\\n\", a, b);\n    return 0;\n}</code></pre>",
                            "real_life_applications": "<p>Pointers and basic variables are used directly in memory-constrained system architectures, such as programming microcontrollers for traffic lights in Kathmandu, or managing register banks in embedded IoT hardware.</p>",
                            "diagrams": "<pre>[ Memory Address: 0x7ffd ] ---> [ 19 ] (int age)\n[ Memory Address: 0x7ffe ] ---> [ 'A' ] (char grade)</pre>",
                            "key_points": "<ul><li>Always declare variables before using them.</li><li>Format specifiers are critical: <code>%d</code> for int, <code>%f</code> for float, <code>%lf</code> for double, and <code>%c</code> for char.</li></ul>",
                            "important_facts": "C is a statically typed language, meaning a variable's data type cannot be altered after declaration.",
                            "formulae": "Memory Range of signed integer: -2^(n-1) to (2^(n-1) - 1), where n = number of bits (32 bits for standard int).",
                            "common_mistakes": "<p>Writing <code>int 1stNumber = 5;</code> which violates the identifier rules (cannot start with a digit).</p><p>Omitting the semicolon at the end of declaration statements.</p>",
                            "mcqs_json": json.dumps([
                                {"q": "Which of the following is a valid variable name in C?", "a": "1variable", "b": "variable_1", "c": "variable-1", "d": "int", "ans": "B", "exp": "Identifiers can contain letters, digits, and underscores, and must not start with digits or match keywords."},
                                {"q": "What is the memory size of a standard double data type in C?", "a": "2 bytes", "b": "4 bytes", "c": "8 bytes", "d": "16 bytes", "ans": "C", "exp": "A double occupies 8 bytes (64 bits) of memory."}
                            ]),
                            "short_questions_json": json.dumps([
                                "What is the difference between float and double in C?",
                                "List four variable naming rules in C Programming."
                            ]),
                            "long_questions_json": json.dumps([
                                "Explain the concept of variable declarations, definitions, and initialization in C with examples. Discuss the role of static data types in memory management."
                            ]),
                            "critical_thinking_questions_json": json.dumps([
                                "What would happen if you assign an integer value representing an ASCII character to a char variable? Write a program to prove your theory."
                            ]),
                            "summary": "<p>C is a statically typed language where variable data types determine memory usage. Identifiers name these variables. Correct format specifiers are required to output their values.</p>",
                            "revision_notes": "<p>Verify format specifiers: %d, %c, %f, %lf. Remember ASCII numbers for 'A' (65) and 'a' (97).</p>",
                            "estimated_reading_time": 10,
                            "difficulty_level": "beginner",
                            "learning_outcomes": "<p>Understand data type boundaries, declare variables, print them using standard I/O format specifiers.</p>"
                        }
                    }
                ]
            },
            {
                "chapter_number": 2,
                "name": "Control Flow Statements",
                "topics": [
                    {
                        "topic_number": 1,
                        "name": "Loops",
                        "subtopics": ["for loop", "while loop", "do-while loop", "Break and Continue statements"],
                        "material": {
                            "title": "Iteration and Loops in C",
                            "learning_objectives": "<ul><li>Master the execution flow of for, while, and do-while loops.</li><li>Understand break and continue modifiers.</li><li>Avoid infinite loops.</li></ul>",
                            "introduction": "<p>Loops allow code blocks to execute repeatedly based on boolean conditional evaluations, which is a core construct in algorithm designs.</p>",
                            "detailed_explanation": "<p>C provides three looping constructs:</p><ul><li><strong>for loop</strong>: Pre-tested loop, ideal when iteration count is known beforehand. Syntax: <code>for(initialization; condition; increment)</code>.</li><li><strong>while loop</strong>: Pre-tested loop, checks condition first. Best when repetition count depends on dynamic runtime inputs.</li><li><strong>do-while loop</strong>: Post-tested loop. Guarantees the code block executes AT LEAST once.</li></ul>",
                            "important_definitions": "<p><strong>Iteration</strong>: One cycle of loop body execution.</p><p><strong>Infinite Loop</strong>: A loop whose termination condition is never satisfied.</p>",
                            "concepts": "<p>Loops depend on loop-control variables. In C, any non-zero value evaluates as true, while zero evaluates as false.</p>",
                            "examples": "<pre><code>for(int i = 0; i < 5; i++) { printf(\"%d \", i); }</code></pre>",
                            "worked_examples": "<p><strong>Problem:</strong> Write a program to compute the factorial of a user-entered number using a while loop.</p><pre><code>#include &lt;stdio.h&gt;\nint main() {\n    int num = 5;\n    long long factorial = 1;\n    int i = 1;\n    while(i <= num) {\n        factorial *= i;\n        i++;\n    }\n    printf(\"Factorial = %lld\\n\", factorial);\n    return 0;\n}</code></pre>",
                            "real_life_applications": "<p>Repeating tasks, such as rendering frames in video engines, checking sensor feeds periodically, or reading lines of files until EOF is reached.</p>",
                            "diagrams": "<pre>[Start] ---> [Init Variable] ---> [Test Condition?] --- (False) ---> [Exit]\n                                       | (True)\n                                  [Execute Body] ---> [Increment] ---> (Test again)</pre>",
                            "key_points": "<ul><li>Ensure the loop variable is modified inside the body to prevent infinite execution loops.</li><li>The do-while loop ends with a semicolon: <code>do { ... } while(cond);</code>.</li></ul>",
                            "important_facts": "The break statement exits the loop immediately, whereas continue skips the remaining statements of the current iteration and jumps to the next loop cycle test/increment.",
                            "formulae": "Number of iterations for <code>for(i=a; i < b; i++)</code> is equal to <code>b - a</code> assuming step is 1 and <code>b >= a</code>.",
                            "common_mistakes": "<p>Putting a semicolon right after the for statement: <code>for(int i=0; i<10; i++);</code>. This turns the loop body into an empty block!</p>",
                            "mcqs_json": json.dumps([
                                {"q": "Which loop is guaranteed to execute at least once?", "a": "for loop", "b": "while loop", "c": "do-while loop", "d": "none of the above", "ans": "C", "exp": "do-while loops evaluate their test condition at the bottom of the loop body."}
                            ]),
                            "short_questions_json": json.dumps([
                                "Differentiate between break and continue statements.",
                                "What is an infinite loop? Show an example in C."
                            ]),
                            "long_questions_json": json.dumps([
                                "Explain the differences in flow control between for, while, and do-while loops, providing sample code and control flow diagrams for each."
                            ]),
                            "critical_thinking_questions_json": json.dumps([
                                "Write a program that prints prime numbers up to 100 using nested loops, optimizing the inner loop limit to the square root of the number."
                            ]),
                            "summary": "<p>Iteration is achieved via loops. Pre-tested loops evaluate conditions first, whereas post-tested loops execute the body first. Modifiers control skip/break patterns.</p>",
                            "revision_notes": "<p>Check loop bounds carefully. Do-while loops always execute once and require a terminating semicolon.</p>",
                            "estimated_reading_time": 15,
                            "difficulty_level": "intermediate",
                            "learning_outcomes": "<p>Implement complex calculations using loops, nested loops, and iteration break triggers.</p>"
                        }
                    }
                ]
            }
        ]

        # Seed chapters, topics, subtopics for C Programming
        for ch_data in c_prog_chapters:
            ch = Chapter(subject_id=sub_csit_c.id, name=ch_data["name"], chapter_number=ch_data["chapter_number"])
            db.session.add(ch)
            db.session.flush()

            for t_data in ch_data["topics"]:
                t = Topic(chapter_id=ch.id, name=t_data["name"], topic_number=t_data["topic_number"])
                db.session.add(t)
                db.session.flush()

                # Add subtopics
                for idx, s_name in enumerate(t_data["subtopics"]):
                    subt = Subtopic(topic_id=t.id, name=s_name, subtopic_number=idx+1)
                    db.session.add(subt)
                
                # Add learning material
                m_data = t_data["material"]
                lm = LearningMaterial(
                    topic_id=t.id,
                    title=m_data["title"],
                    learning_objectives=m_data["learning_objectives"],
                    introduction=m_data["introduction"],
                    detailed_explanation=m_data["detailed_explanation"],
                    important_definitions=m_data["important_definitions"],
                    concepts=m_data["concepts"],
                    examples=m_data["examples"],
                    worked_examples=m_data["worked_examples"],
                    real_life_applications=m_data["real_life_applications"],
                    diagrams=m_data["diagrams"],
                    key_points=m_data["key_points"],
                    important_facts=m_data["important_facts"],
                    formulae=m_data["formulae"],
                    common_mistakes=m_data["common_mistakes"],
                    mcqs_json=m_data["mcqs_json"],
                    short_questions_json=m_data["short_questions_json"],
                    long_questions_json=m_data["long_questions_json"],
                    critical_thinking_questions_json=m_data["critical_thinking_questions_json"],
                    summary=m_data["summary"],
                    revision_notes=m_data["revision_notes"],
                    estimated_reading_time=m_data["estimated_reading_time"],
                    difficulty_level=m_data["difficulty_level"],
                    learning_outcomes=m_data["learning_outcomes"]
                )
                db.session.add(lm)
                
                # Create default flashcards for this chapter
                db.session.add(Flashcard(subject_id=sub_csit_c.id, chapter_id=ch.id, front=f"What is primitive data type in C?", back="A basic built-in data type like int, char, float, or double."))
                db.session.add(Flashcard(subject_id=sub_csit_c.id, chapter_id=ch.id, front=f"How many bytes does int occupy typically?", back="4 bytes on modern systems."))
                db.session.add(Flashcard(subject_id=sub_csit_c.id, chapter_id=ch.id, front=f"What is ASCII value of character 'A'?", back="65"))
                db.session.add(Flashcard(subject_id=sub_csit_c.id, chapter_id=ch.id, front=f"Differentiate pre-test vs post-test loops.", back="Pre-test (for/while) evaluates condition first; post-test (do-while) executes body once before checking condition."))
                
                # Seed diagnostic Assessment Questions linked to this chapter
                db.session.add(AssessmentQuestion(
                    subject_id=sub_csit_c.id, chapter_id=ch.id,
                    question_text=f"Which data type in C is used to store decimal fractional numbers with single-precision?",
                    option_a="int", option_b="float", option_c="char", option_d="double",
                    correct_answer="B", difficulty="beginner", question_type="conceptual"
                ))
                db.session.add(AssessmentQuestion(
                    subject_id=sub_csit_c.id, chapter_id=ch.id,
                    question_text=f"What will be the output of for(int i=0; i<3; i++) { '{ printf(\"%d\", i); }' } in C?",
                    option_a="012", option_b="123", option_c="0123", option_d="Error",
                    correct_answer="A", difficulty="intermediate", question_type="problem_solving"
                ))

        # --- SEED SOME DUMMY (YET DETAILED AND ORIGINAL) MATERIALS FOR CLASS 8 MATHEMATICS ---
        ch8_math_ch = Chapter(subject_id=sub_c8_math.id, name="Sets and Cardinality", chapter_number=1)
        db.session.add(ch8_math_ch)
        db.session.flush()
        
        ch8_math_top = Topic(chapter_id=ch8_math_ch.id, name="Venn Diagrams", topic_number=1)
        db.session.add(ch8_math_top)
        db.session.flush()
        
        db.session.add(Subtopic(topic_id=ch8_math_top.id, name="Introduction to Venn Diagrams", subtopic_number=1))
        db.session.add(Subtopic(topic_id=ch8_math_top.id, name="Two-set Venn Diagram Word Problems", subtopic_number=2))
        
        lm_c8 = LearningMaterial(
            topic_id=ch8_math_top.id,
            title="Introduction to Venn Diagrams and Cardinality for Class 8",
            learning_objectives="<ul><li>Define union and intersection of two sets.</li><li>Represent set relations graphically using Venn Diagrams.</li><li>Solve simple cardinality word problems.</li></ul>",
            introduction="<p>Venn diagrams, introduced by John Venn in 1880, represent set relationships using closed shapes, typically circles inside a rectangle denoting the universal set.</p>",
            detailed_explanation="<p>Given two sets A and B, the cardinality formula relating their union and intersection is: <code>n(A U B) = n(A) + n(B) - n(A ∩ B)</code>. If the sets are disjoint (have no elements in common), then their intersection is 0, and the formula simplifies to <code>n(A U B) = n(A) + n(B)</code>.</p>",
            important_definitions="<strong>Cardinality</strong>: The number of elements inside a set, denoted as n(A).",
            concepts="<p>The region of intersection (overlapping area) represents common elements: <code>A ∩ B</code>. The entire circle area combined represents the union: <code>A U B</code>.</p>",
            examples="<p>Set A = {1, 2, 3}, Set B = {3, 4, 5}. Union A U B = {1, 2, 3, 4, 5}. Intersection A ∩ B = {3}.</p>",
            worked_examples="<p><strong>Problem:</strong> In a class of 40 students, 25 like Mathematics, 20 like Science, and 10 like both. How many like neither?</p><p><strong>Solution:</strong> Universal set n(U) = 40. Math n(M) = 25. Science n(S) = 20. Both n(M ∩ S) = 10. Using formula: n(M U S) = n(M) + n(S) - n(M ∩ S) = 25 + 20 - 10 = 35. Therefore, students liking neither = n(U) - n(M U S) = 40 - 35 = 5 students.</p>",
            real_life_applications="<p>Used to represent demographics in census data in Nepal (e.g. bilingual speakers who speak Nepali and Newari).</p>",
            diagrams="<pre>  Universal Set (U) [40]\n  [  ( Math [15] ) ( Both [10] ) ( Science [10] )  ]\n  Outside circles: 5 students neither</pre>",
            key_points="Always compute the intersection area first when filling a Venn diagram from word problems.",
            important_facts="Intersection represents 'AND', Union represents 'OR'.",
            formulae="n(A U B) = n(A) + n(B) - n(A ∩ B)\nn(U) = n(A U B) + n(neither)",
            common_mistakes="Forgetting to subtract the intersection when finding students who like Math ONLY (e.g., writing 25 instead of 25 - 10 = 15).",
            mcqs_json=json.dumps([
                {"q": "If n(A) = 15, n(B) = 12, and n(A ∩ B) = 5, what is n(A U B)?", "a": "27", "b": "22", "c": "10", "d": "32", "ans": "B", "exp": "15 + 12 - 5 = 22"}
            ]),
            short_questions_json=json.dumps([
                "Define a universal set with an example.",
                "Write the cardinality relation for two overlapping sets A and B."
            ]),
            long_questions_json=json.dumps([
                "In a survey of 100 tourist visitors in Pokhara, 65 visited Phewa Lake, 45 visited Davis Falls, and 20 visited both. Represent this on a Venn diagram and calculate how many visited Phewa Lake only."
            ]),
            critical_thinking_questions_json=json.dumps([
                "How would you represent three overlapping sets A, B, and C in a Venn diagram? Derive the general formula for n(A U B U C)."
            ]),
            summary="Venn diagrams visualize set unions and intersections. The cardinality formula calculates elements of sets dynamically.",
            revision_notes="Always draw Venn diagrams inside a rectangle representing the universal set.",
            estimated_reading_time=12,
            difficulty_level="beginner",
            learning_outcomes="Understand cardinality and solve overlapping set problems using Venn diagrams."
        )
        db.session.add(lm_c8)
        
        # Add basic flashcards
        db.session.add(Flashcard(subject_id=sub_c8_math.id, chapter_id=ch8_math_ch.id, front="What is the union of Sets A and B?", back="A set containing all elements from both A and B without duplicates."))
        db.session.add(Flashcard(subject_id=sub_c8_math.id, chapter_id=ch8_math_ch.id, front="What does n(A) represent?", back="The cardinality (number of elements) of set A."))
        
        # Add basic diagnostic assessment questions
        db.session.add(AssessmentQuestion(
            subject_id=sub_c8_math.id, chapter_id=ch8_math_ch.id,
            question_text="If n(A)=10, n(B)=8, and sets A and B are disjoint, what is n(A U B)?",
            option_a="18", option_b="10", option_c="8", option_d="2",
            correct_answer="A", difficulty="beginner", question_type="conceptual"
        ))
        db.session.add(AssessmentQuestion(
            subject_id=sub_c8_math.id, chapter_id=ch8_math_ch.id,
            question_text="In a Venn diagram, what geometric shape is typically used to represent the Universal Set?",
            option_a="Circle", option_b="Triangle", option_c="Rectangle", option_d="Oval",
            correct_answer="C", difficulty="beginner", question_type="conceptual"
        ))

        # Seed other subjects with a single default chapter & topic so that the database structure remains uniform
        subjects_all = Subject.query.all()
        print(f"Seeding default curriculum structures for all {len(subjects_all)} subjects...")
        
        for s in subjects_all:
            # Skip if already has chapters
            if Chapter.query.filter_by(subject_id=s.id).first():
                continue
                
            ch = Chapter(subject_id=s.id, name="Unit 1: Introduction and Core Concepts", chapter_number=1)
            db.session.add(ch)
            db.session.flush()
            
            t = Topic(chapter_id=ch.id, name="Fundamentals and Applications", topic_number=1)
            db.session.add(t)
            db.session.flush()
            
            subt = Subtopic(topic_id=t.id, name="Overview", subtopic_number=1)
            db.session.add(subt)
            
            lm = LearningMaterial(
                topic_id=t.id,
                title=f"Fundamentals of {s.name}",
                learning_objectives=f"<ul><li>Understand the foundational concepts of {s.name}.</li><li>Apply theories of {s.name} to solve basic problems.</li></ul>",
                introduction=f"<p>Welcome to the digital textbook study material for {s.name}. This unit details the fundamental framework, terminology, and application profiles of this subject area.</p>",
                detailed_explanation=f"<p>This subject, {s.name}, forms a crucial component of the standard curriculum. It explores the principles, methods, and practices required to master this discipline. Detailed study ensures success in assessments and builds real-world professional competencies.</p>",
                important_definitions=f"<p><strong>{s.name}</strong>: The systematic study of concepts, rules, structures, and techniques underlying this field of education.</p>",
                concepts=f"<p>Core paradigms and frameworks are discussed in this section. Students are advised to review these details regularly.</p>",
                examples=f"<p>Practical cases and sample applications demonstrate the direct mapping of theory to practice.</p>",
                worked_examples=f"<p>Review past question papers and solve the numerical and conceptual exercises presented here.</p>",
                real_life_applications=f"<p>This subject finds direct application across Nepalese educational institutes, corporate sectors, and technology infrastructures.</p>",
                diagrams=f"<pre>[Foundational Core] ---> [Interactive Processes] ---> [Advanced Implementation]</pre>",
                key_points=f"Focus on the primary definitions and core equations.",
                important_facts="Continuous revision is critical to mastering this content.",
                formulae="Refer to standard equations in the curriculum guidelines.",
                common_mistakes="Mixing up basic terminologies and ignoring core principles.",
                mcqs_json=json.dumps([
                    {"q": f"What is the primary study focus of {s.name}?", "a": "Theoretical foundation", "b": "Practical implementation", "c": "Conceptual frameworks", "d": "All of the above", "ans": "D", "exp": "This subject covers theories, concepts, and practical implementations."}
                ]),
                short_questions_json=json.dumps([
                    "List two key areas of study in this unit.",
                    "Why is this subject important?"
                ]),
                long_questions_json=json.dumps([
                    f"Write a comprehensive essay describing the evolution of {s.name} and discuss its practical applications in modern Nepal."
                ]),
                critical_thinking_questions_json=json.dumps([
                    f"Analyze how recent technological and social advancements have shaped the core theories of {s.name}."
                ]),
                summary=f"<p>This unit outlined the basic pillars of {s.name}. Keep revising.</p>",
                revision_notes=f"<p>Review key terms and practice diagrams weekly.</p>",
                estimated_reading_time=15,
                difficulty_level="intermediate",
                learning_outcomes=f"<p>Acquire foundational knowledge and solve basic problems in {s.name}.</p>"
            )
            db.session.add(lm)
            
            # Add default flashcards
            db.session.add(Flashcard(subject_id=s.id, chapter_id=ch.id, front=f"Define the scope of {s.name}.", back="The systematic understanding and implementation of its core principles."))
            
            # Add default assessment questions
            db.session.add(AssessmentQuestion(
                subject_id=s.id, chapter_id=ch.id,
                question_text=f"Which of the following is a primary core topic in {s.name}?",
                option_a="Foundational concepts", option_b="Irrelevant subjects", option_c="External data", option_d="None of the above",
                correct_answer="A", difficulty="beginner", question_type="conceptual"
            ))
            db.session.add(AssessmentQuestion(
                subject_id=s.id, chapter_id=ch.id,
                question_text=f"True or False: Mastering the fundamentals of {s.name} requires solving practice exercises.",
                option_a="True", option_b="False", option_c="Both", option_d="None",
                correct_answer="A", difficulty="intermediate", question_type="conceptual"
            ))

        db.session.commit()
        print("Curriculum databases, detailed chapters, topics, subtopics, textbooks, flashcards, and diagnostic questions seeded successfully!")

if __name__ == "__main__":
    seed_curriculum()
