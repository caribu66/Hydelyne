import { gql } from '@apollo/client'

export const CREW_MEMBERS_QUERY = gql`
  query CrewMembers($availability: AvailabilityStatus, $search: String, $limit: Int, $offset: Int) {
    crewMembers(availability: $availability, search: $search, limit: $limit, offset: $offset) {
      id
      fullName
      nationality
      countryOfResidence
      dateOfBirth
      gender
      languages
      flyingPoint
      email
      phone
      availabilityStatus
      availabilityDate
      profileCompletenessScore
      yearsOfExperience
      education
      professionalSummary
      geographicalExperience
      systemsExperience
      trainingQualifications
      certifications { id certType certNumber issuingBody issueDate expiryDate renewalDate status verificationStatus documentRef }
      workHistory { id clientName projectName country location projectType role responsibilities startDate endDate status }
      tags
      passport {
        number
        expiry
        issuingCountry
      }
      visa {
        type
        expiry
      }
      medical {
        status
        expiry
        provider
      }
      insurance {
        provider
        expiry
      }
      createdAt
      updatedAt
    }
  }
`

export const ME_QUERY = gql`
  query Me {
    me { id fullName email role }
  }
`

export const CREW_MEMBER_QUERY = gql`
  query CrewMember($id: String!) {
    crewMember(id: $id) {
      id
      fullName
      nationality
      email
      phone
      availabilityStatus
      tags
    }
  }
`

export const EXPIRING_CERTS_QUERY = gql`
  query ExpiringCerts($days: Int) {
    expiringCertifications(days: $days) {
      id
      certType
      certNumber
      expiryDate
      status
      verificationStatus
    }
  }
`

export const PENDING_REVIEWS_QUERY = gql`
  query PendingReviews {
    pendingReviews {
      id
      fileName
      classification
      extractionStatus
    }
  }
`

export const CREW_SUMMARY_QUERY = gql`
  query CrewSummary($crewId: String!) {
    crewSummary(crewId: $crewId)
  }
`

export const DOCUMENTS_BY_CREW_QUERY = gql`
  query DocumentsByCrew($crewId: String!) {
    documentsByCrew(crewId: $crewId) {
      id
      fileName
      fileType
      fileSize
      classification
      extractionStatus
      extractedText
      extractedData
      extractionConfidence
      uploadedAt
    }
  }
`

export const LOGIN_MUTATION = gql`
  mutation Login($email: String!, $password: String!) {
    login(email: $email, password: $password) {
      success
      message
      token
      user {
        id
        fullName
        email
        role
      }
    }
  }
`

export const LOGOUT_MUTATION = gql`
  mutation Logout {
    logout
  }
`

export const QUERY_CREW = gql`
  query QueryCrew($query: String!) {
    queryCrew(query: $query) {
      intent
      query
      summary
      results
      criteria
      totalIssues
      crewId
      crewName
    }
  }
`

export const CREATE_CREW_MEMBER = gql`
  mutation CreateCrewMember($fullName: String!, $email: String, $phone: String, $nationality: String) {
    createCrewMember(fullName: $fullName, email: $email, phone: $phone, nationality: $nationality) {
      id
      fullName
      email
      phone
      nationality
      availabilityStatus
    }
  }
`

export const DELETE_CREW_MEMBER = gql`
  mutation DeleteCrewMember($id: String!) {
    deleteCrewMember(id: $id)
  }
`

export const VERIFY_CERTIFICATION = gql`
  mutation VerifyCertification($id: String!, $status: VerificationStatus!) {
    verifyCertification(id: $id, status: $status) {
      id
      certType
      status
      verificationStatus
      documentRef
      issueDate
      expiryDate
    }
  }
`
