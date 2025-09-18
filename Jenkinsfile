// pipeline {
//   agent any
//   environment {
//     py = "py"
//   }
//   stages {
//     stage('Checkout') {
//       steps { checkout scm }
//     }
//     stage('Install deps') {
//       steps {
//         sh "${env.py} -m pip install -q -r requirements.txt"
//       }
//     }
//     stage('Prepare reports') {
//       steps {
//         sh '''
//           mkdir -p reports
//           # copy sample_reports (in repo) into reports
//           cp -r sample_reports/* reports/ || true
//           ls -la reports || true
//         '''
//       }
//     }
//     stage('Run parser') {
//       steps {
//         sh "${env.py} scripts/parse_cucumber_reports.py -i reports -o report_summary.json"
//         sh "cat summary.md || true"
//       }
//       post {
//         always {
//           archiveArtifacts artifacts: 'report_summary.json, summary.md', fingerprint: true
//         }
//       }
//     }
//     stage('Send summary (email)') {
//       steps {
//         script {
//           // option A: use email-ext plugin if installed - you must configure SMTP in Jenkins
//           def summaryText = readFile('summary.md')
//           if (env.SEND_EMAIL == 'true') {
//             // If you have the Email Extension plugin
//             emailext (
//               subject: "POC QA Summary - Build ${env.BUILD_NUMBER}",
//               body: """<pre>${summaryText}</pre>""",
//               to: "${params.EMAIL_TO ?: 'client@example.com'}"
//             )
//           } else {
//             echo "SEND_EMAIL != true - not sending email. To enable set SEND_EMAIL=true in job env."
//             echo summaryText
//           }
//         }
//       }
//     }
//   }
// }


pipeline {
    agent any
    environment {
        py = "py" // Windows Python launcher
    }
    stages {

        stage('Checkout') {
            steps { 
                checkout scm 
            }
        }

        stage('Install deps') {
            steps {
                // Install dependencies using pip
                bat "${env.py} -m pip install -q -r requirements.txt"
            }
        }

        stage('Prepare reports') {
            steps {
                // Create reports folder and copy sample reports
                bat """
                    if not exist reports mkdir reports
                    xcopy /E /I sample_reports\\* reports\\ >nul 2>&1
                    dir reports
                """
            }
        }

        stage('Run parser') {
            steps {
                // Run Python parser
                bat "${env.py} scripts\\parse_cucumber_reports.py -i reports -o report_summary.json"

                // Display summary if it exists
                bat """
                    if exist summary.md (
                        type summary.md
                    ) else (
                        echo No summary.md found
                    )
                """
            }
            post {
                always {
                    // Archive artifacts (JSON + MD summary)
                    archiveArtifacts artifacts: 'report_summary.json,summary.md', fingerprint: true
                }
            }
        }

        stage('Send summary (email)') {
            steps {
                script {
                    // Read summary.md if it exists
                    def summaryText = fileExists('summary.md') ? readFile('summary.md') : "No summary generated."
                    
                    if (env.SEND_EMAIL == 'true') {
                        // Send email using Email Extension plugin
                        emailext (
                            subject: "POC QA Summary - Build ${env.BUILD_NUMBER}",
                            body: """<pre>${summaryText}</pre>""",
                            to: "${params.EMAIL_TO ?: 'client@example.com'}"
                        )
                    } else {
                        echo "SEND_EMAIL != true - not sending email."
                        echo summaryText
                    }
                }
            }
        }
    }
}

