# TASKNEST: Student Task Manager

## Overview

**TaskNest** is a dedicated Student Task Manager designed to help learners stay organized, meet deadlines, and successfully manage their academic workload. It goes beyond a basic to-do list by providing **smart reminders**, **progress tracking**, and **timely alerts** specifically for crucial academic milestones like CATs (Continuous Assessment Tests) and Exams.

Our goal is to create a seamless, user-friendly platform that minimizes academic stress and maximizes student productivity.

---

## Core Features

# Modelling the TaskNest System

An overview of the system's implementation is shown by the following diagrams below

## 1. Use case Interaction

![usecasediagram](TaskNest/documentation/use_case.drawio.svg)

## 2. Class Diagram

![classdiagram](class_diagram.drawio.svg)

TaskNest is structured around several collaborative modules to deliver a powerful experience:

| Module                      | Description                                                                                                                 | Primary Team Focus |
| :-------------------------- | :-------------------------------------------------------------------------------------------------------------------------- | :----------------- |
| **Task Management**         | Comprehensive to-do list functionality, allowing users to create, categorize, and prioritize tasks with specific deadlines. | Functional         |
| **Reminder & Notification** | Smart, scheduled alerts for upcoming task deadlines, assignments, and study sessions.                                       | Functional         |
| **Exam & CAT Scheduler**    | Dedicated module for scheduling and providing timely alerts for Continuous Assessment Tests (CATs) and Exams.               | Functional         |
| **Progress Tracking**       | Visualization of student activity and goal achievement using records and tracking metrics.                                  | Database           |
| **User Authentication**     | Secure handling of user credentials, including sign-up, login, and data protection.                                         | Database           |
| **UI/UX & Reporting**       | Intuitive interface design, visual data reporting (graphs), and a seamless user experience across all devices.              | Design             |

---

## Technology Stack

_(Note: Please replace the placeholders below with the actual technologies your team selects.)_

| Component      | Technology / Language | Purpose                                       |
| :------------- | :-------------------- | :-------------------------------------------- |
| **Frontend**   | css                   | User Interface and Interaction                |
| **Backend**    | Python                | API, Logic, and Authentication                |
| **Database**   | PostgreSQL            | Schema implementation and secure data storage |
| **Deployment** | Netlify               | Hosting and environment management            |

---

## Team Structure and Roles

The TaskNest development team is organized into specialized teams to ensure high-quality execution across all aspects of the project.

| Team                        | Members                        | Core Responsibilities                                                                                                                                     |
| :-------------------------- | :----------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Functional**              | Angela, Sajjad, Gabriel, Benir | Defining core features, writing detailed workflow specifications, and ensuring the system solves the main problem statement (the "what").                 |
| **Design**                  | Tabitha, Natalie, Angela       | Developing UI/UX layouts (wireframes, mockups), establishing visual branding, and ensuring system accessibility (the "look and feel").                    |
| **Database**                | Maxwell, Shone                 | Designing and implementing the database schema (ER diagrams, SQL), managing data flow, and handling security/authentication (the "storage and security"). |
| **Testing & Documentation** | Benir                          | Writing test cases for all modules, tracking bugs, maintaining the primary structure and consistency of the final system documentation.                   |

---

## Contribution and Collaboration

This project operates on a collaborative model where every module involves cross-functional teamwork, with clear Primary and Supporting roles to guide ownership.

1.  **Fork** the repository.
2.  **Clone** your forked repository.
3.  Create a descriptive **branch** for your feature or fix (e.g., `feat/add-reminder-logic` or `fix/auth-bug`).
4.  Commit your changes following a clear convention.
5.  Push your branch and open a **Pull Request (PR)** to the `main` branch.
