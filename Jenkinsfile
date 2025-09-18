pipeline {
  agent any
  environment {
    py = "py"
  }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Install deps') {
      steps {
        bat "${env.py} -m pip install -q -r requirements.txt"
      }
    }
    stage('Prepare reports') {
      steps {
        bat """
          if exist reports rd /s /q reports
          mkdir reports
          xcopy /E /I /Y sample_reports\\* reports\\
          dir reports
        """
      }
    }
    stage('Run parser') {
      steps {
        bat "${env.py} scripts\\parse_cucumber_reports.py -i reports -o report_summary.json"
        bat "type summary.md"
      }
      post {
        always {
          archiveArtifacts artifacts: 'report_summary.json, summary.md', fingerprint: true
        }
      }
    }
    stage('Send summary (email)') {
      steps {
        script {
          // option A: use email-ext plugin if installed - you must configure SMTP in Jenkins
          def summaryText = readFile('summary.md')
          if (env.SEND_EMAIL == 'true') {
            // If you have the Email Extension plugin
            emailext (
              subject: "POC QA Summary - Build ${env.BUILD_NUMBER}",
              body: """<pre>${summaryText}</pre>""",
              to: "${params.EMAIL_TO ?: 'client@example.com'}"
            )
          } else {
            echo "SEND_EMAIL != true - not sending email. To enable set SEND_EMAIL=true in job env."
            echo summaryText
          }
        }
      }
    }
  }
}


