import { gql } from '@apollo/client'

export const CREW_MEMBERS_QUERY = gql`
  query CrewMembers($availability: AvailabilityStatus, $search: String, $limit: Int, $offset: Int) {
    crewMembers(availability: $availability, search: $search, limit: $limit, offset: $offset) {
      id
      fullName
      nationality
      countryOfResidence
      gender
      languages
      flyingPoint
      availabilityStatus
      availabilityDate
      profileCompletenessScore
      yearsOfExperience
      education
      professionalSummary
      geographicalExperience
      systemsExperience
      trainingQualifications
      tags
      medical { status expiry }
      certifications { id certType issueDate expiryDate status verificationStatus }
      createdAt
      updatedAt
    }
  }
`

export const CREW_MEMBER_DETAIL_QUERY = gql`
  query CrewMemberDetail($id: String!) {
    crewMember(id: $id) {
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
        policyNumber
        coverage
        expiry
      }
      internalNotes
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
  mutation CreateCrewMember($fullName: String!, $email: String, $phone: String, $nationality: String, $cvSubmission: Boolean!, $confirmDistinct: Boolean!) {
    createCrewMember(fullName: $fullName, email: $email, phone: $phone, nationality: $nationality, cvSubmission: $cvSubmission, confirmDistinct: $confirmDistinct) {
      id
      fullName
      email
      phone
      nationality
      availabilityStatus
    }
  }
`

export const CV_REVIEWS_QUERY = gql`
  query CvReviews($limit: Int!, $offset: Int!) {
    cvReviews(limit: $limit, offset: $offset) {
      id
      documentId
      crewMemberId
      status
      proposedData
      submittedBy
      reviewedBy
      reviewNote
      createdAt
      reviewedAt
    }
  }
`

export const APPROVE_CV_REVIEW = gql`
  mutation ApproveCvReview($reviewId: String!, $approvedData: String!, $note: String) {
    approveCvReview(reviewId: $reviewId, approvedData: $approvedData, note: $note)
  }
`

export const REJECT_CV_REVIEW = gql`
  mutation RejectCvReview($reviewId: String!, $note: String!) {
    rejectCvReview(reviewId: $reviewId, note: $note)
  }
`

export const STAFF_USERS_QUERY = gql`
  query StaffUsers($limit: Int!, $offset: Int!) {
    crewMembers(limit: $limit, offset: $offset) {
      id
      fullName
      email
      role
    }
  }
`

export const SET_STAFF_ROLE = gql`
  mutation SetStaffRole($userId: String!, $enabled: Boolean!) {
    setStaffRole(userId: $userId, enabled: $enabled) {
      id
      role
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

export const PROJECTS_QUERY = gql`
  query Projects($status: ProjectStatus) {
    projects(status: $status) {
      id
      clientName
      projectName
      projectType
      location
      country
      startDate
      endDate
      status
    }
  }
`

export const SEARCH_VESSELS_QUERY = gql`
  query SearchVessels($name: String!, $limit: Int) {
    vesselSearch(name: $name, limit: $limit) {
      vessels {
        id
        name
        imo
        mmsi
        callsign
        vesselType
        flag
        length
        width
        yearBuilt
      }
      cached
      provider
      upstreamCount
      configured
    }
  }
`

export const VESSEL_POSITION_QUERY = gql`
  query VesselPosition($vesselId: String!, $idType: VesselIdType) {
    vesselPosition(vesselId: $vesselId, idType: $idType) {
      mmsi
      imo
      latitude
      longitude
      sog
      cog
      heading
      timestamp
      destination
      eta
    }
  }
`

export const CREATE_CAMPAIGN_ASSIGNMENT = gql`
  mutation CreateCampaignAssignment($input: CreateCampaignAssignmentInput!) {
    createCampaignAssignment(input: $input) {
      id
      crewMemberId
      projectId
      vesselImo
      roleOnBoard
      startDate
      endDate
      status
      agreedDayRate
      notes
      createdAt
      updatedAt
      crewName
      vesselName
      projectName
    }
  }
`

export const UPDATE_CAMPAIGN_ASSIGNMENT_STATUS = gql`
  mutation UpdateCampaignAssignmentStatus($assignmentId: String!, $status: CampaignAssignmentStatus!) {
    updateCampaignAssignmentStatus(assignmentId: $assignmentId, status: $status) {
      id
      status
      updatedAt
    }
  }
`

export const VESSEL_ROSTER_QUERY = gql`
  query VesselRoster($imo: String!) {
    vesselRoster(imo: $imo) {
      id
      crewMemberId
      projectId
      vesselImo
      roleOnBoard
      startDate
      endDate
      status
      agreedDayRate
      notes
      createdAt
      updatedAt
      crewName
      vesselName
      projectName
    }
  }
`

export const CAMPAIGN_ASSIGNMENTS_QUERY = gql`
  query CampaignAssignments($vesselImo: String, $projectId: String, $crewId: String, $status: CampaignAssignmentStatus) {
    campaignAssignments(vesselImo: $vesselImo, projectId: $projectId, crewId: $crewId, status: $status) {
      id
      crewMemberId
      projectId
      vesselImo
      roleOnBoard
      startDate
      endDate
      status
      agreedDayRate
      notes
      createdAt
      updatedAt
      crewName
      vesselName
      projectName
    }
  }
`
