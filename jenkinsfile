pipeline {
  agent any
  environment {
    PY = "python3"
  }
  stages {
    stage('Checkout') {
      steps { checkout scm }
    }
    stage('Install deps') {
      steps {
        sh "${env.PY} -m pip install -q -r requirements.txt"
      }
    }
    stage('Prepare reports') {
      steps {
        sh '''
          mkdir -p reports
          # copy sample_reports (in repo) into reports
          cp -r sample_reports/* reports/ || true
          ls -la reports || true
        '''
      }
    }
    stage('Run parser') {
      steps {
        sh "${env.PY} scripts/parse_cucumber_reports.py -i reports -o report_summary.json"
        sh "cat summary.md || true"
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
