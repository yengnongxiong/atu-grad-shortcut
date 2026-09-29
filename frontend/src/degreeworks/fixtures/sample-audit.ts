/**
 * A synthetic Degree Works audit (fake student, fake ID) laid out the way pdf.js reads a real
 * one: one string per visual line, wrapped cells on the next line, page headers mid-block.
 */
export const SAMPLE_AUDIT: string[] = `Arkansas Tech University Sample, Student - T00000000
Arkansas Tech University
Degree progress
Student name Sample, Student
Overall GPA
Student ID T00000000
58% 3.500
Degree BS Computer Science
Audit date 09/01/2026 9:00 AM
Requirements
Level Undergraduate Classification Sophomore Major Computer Science (BS) Program Bachelor of Science College Science, Tech, Engr, Math
BS in Computer Science INCOMPLETE
Credits required: 120 Credits applied: 40 Catalog year: 2025-2026
Still needed: You must complete all prescribed degree requirements below and reach a
Minimum of 120 Hours Required for Bachelor
General Education Requirements Still needed: See General Education Requirements BS in Computer Sci section
General Education Requirements BS in Computer Sci INCOMPLETE
Credits required: 30 Credits applied: 16 Catalog year: 2025-2026
Course Title Grade Credits Term Course
GENERAL EDUCATION REQUIREMENTS
Orientation TECH 1001 ORIENTATION TO UNIVERSITY B 1 Fall Term 2025
Composition I (C or better) ENGL 1013 COMPOSITION I CE 3 Spring Term
2024
Satisfied by: AP10 - ENGLISH LITERATURE/COMP - Credit by AP Exam
Composition II (C or better) ENGL 1023 COMPOSITION II A 3 Spring Term 2026
SCIENCE WITH LAB COURSE Still needed: Choose from 1 of the following:
SCIENCE WITH LAB COURSE You must complete all of the following:
Lecture Requirement 1 Class in PHSC 1013 or 1053 or CHEM 1113
Lab Requirement 1 Class in PHSC 1021 or 1051 or CHEM 1111
Science with Lab 1 Class in BIOL 1004 or 1014 or 1114 or GEOL 1014 or
2024 or PHYS 2014
US History or Government POLS 2003 AMERICAN GOVERNMENT CE 3 Fall Term 2025
Arkansas Tech University Sample, Student - T00000000
Satisfied by: CL01 - AMERICAN GOVERNMENT - Credit by CLEP Exam
Fine Arts and Humanities ENGL 2003 INTRO TO LITERATURE TB 3 Summer Term 2025
Satisfied by: ENGL 2113 - INTRODUCTION TO LITERATURE - Sample Community College
Social Sciences SOC 1003 INTRODUCTORY SOCIOLOGY CE 3 Fall Term 2025
Satisfied by: CL20 - INTRODUCTORY SOCIOLOGY - Credit by CLEP Exam
Still needed: 1 Class in ECON 2003 or 2013 or HIST 1503 or
1513 or PSY 2003
Major in Computer Science INCOMPLETE
Credits required: 58 Credits applied: 28 Catalog year: 2025-2026
Course Title Grade Credits Term Course
Programming I and Programming I Lab COMS 1013 PROGRAMMING FOUNDATIONS I A 3 Fall Term 2025
COMS 1011 PROGRAMMING FOUNDATIONS I P 1 Fall Term
LAB 2025
Scripting Languages COMS 2163 SCRIPTING LANGUAGES IP (3) Fall Term 2026
Computer Hardware and Architecture COMS 2703 COMP HARDWARE & B 3 Spring Term
ARCHITECTURE 2026
Programming II COMS 2203 PROGRAMMING FOUNDATIONS II C 3 Spring Term 2026
Data Structures COMS 2213 DATA STRUCTURES IP (3) Fall Term 2026
Algorithm Design and Analysis Still needed: 1 Class in COMS 3213
Capstone Still needed: 1 Class in COMS 4913
Major Support Courses - Computer Science INCOMPLETE
Credits required: 32 Credits applied: 20 Catalog year: 2025-2026
Calculus I MATH 2914 CALCULUS I A 4 Fall Term 2025
Discrete Mathematics MATH 2703 DISCRETE MATHEMATICS W 3 Spring Term 2026
Approved electives Still needed: 9 Credits in @ 3@ or 4@ Except @ @ with attribute = LD
Not Used and Not Eligible for Financial Aid Credits applied: 4 Classes applied: 2
Course Title Grade Credits Term Repeated
COMS 1403 ORIENT TO COMP INFO/TECH CE 3 Spring Term 2025
Satisfied by: AP35 - COMPUTER SCIENCE PRINCIPLES - Credit by AP Exam
COMS 1411 COMPUTER/INFO SCI LAB CE 1 Spring Term 2025
Satisfied by: AP35 - COMPUTER SCIENCE PRINCIPLES - Credit by AP Exam
In-progress Credits applied: 6 Classes applied: 2
Course Title Grade Credits Term Repeated
COMS 2163 SCRIPTING LANGUAGES IP (3) Fall Term 2026
COMS 2213 DATA STRUCTURES IP (3) Fall Term 2026
Legend
Complete Not complete
Ellucian Degree Works - © Copyright 1995-2026 Ellucian Company L.P. and its affiliates`.split('\n')
