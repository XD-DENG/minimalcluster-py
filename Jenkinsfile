pipeline {
  agent {
    docker {
      image 'python:2-alpine'
    }

  }
  stages {
    stage('Build') {
      steps {
        sh 'echo \'Building the project\''
      }
    }
    stage('Testing') {
      steps {
        echo 'Testing the project'
      }
    }
    stage('Final Message') {
      steps {
        echo 'Project tested'
      }
    }
  }
}